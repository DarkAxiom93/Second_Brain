"""CLI for bounded scan or explicit synchronous recovery of one Agent Run."""

import argparse
import json
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agent_planning.dependencies import configured_embedding_provider_available
from app.agent_runs import executor, recovery, service
from app.db.session import get_engine
from app.embeddings import get_embedding_provider


def _verify_operator_database() -> None:
    engine = get_engine()
    url = make_url(str(engine.url))
    if url.host != "127.0.0.1" or url.database != "second_brain":
        raise SystemExit("operator recovery requires the verified development database")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != "second_brain":
            raise SystemExit("operator recovery database identity mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=uuid.UUID)
    args = parser.parse_args()
    try:
        _verify_operator_database()
        with Session(get_engine()) as session:
            if args.run_id is None:
                for finding in recovery.scan(session):
                    print(json.dumps(finding.safe_dict(), sort_keys=True))
                session.rollback()
                return 0
            claim = recovery.prepare_one(session, args.run_id)
            session.commit()
            if claim is not None:
                while True:
                    reserved = executor.reserve_next(
                        session,
                        claim,
                        provider_available=configured_embedding_provider_available(),
                    )
                    session.commit()
                    if reserved is None:
                        break
                    step, invocation, timeout = reserved
                    output, error = executor.call_reserved_tool(
                        session,
                        claim,
                        step,
                        invocation,
                        timeout,
                        get_embedding_provider,
                    )
                    session.rollback()
                    keep_going = executor.finalize_invocation(
                        session,
                        claim,
                        step_id=step.id,
                        invocation_id=invocation.id,
                        output=output,
                        safe_error_code=error,
                    )
                    session.commit()
                    if not keep_going:
                        break
                executor.complete_run(session, claim)
                session.commit()
            print(json.dumps({"run_id": str(args.run_id), "recovery": "reconciled"}))
        return 0
    except service.AgentRunNotFoundError:
        print(json.dumps({"error": "agent_run_not_found"}))
        return 2
    except Exception:
        print(json.dumps({"error": "recovery_unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
