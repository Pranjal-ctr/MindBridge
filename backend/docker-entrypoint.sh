#!/bin/sh
# Kio Backend container entrypoint.
#
#   serve     (default) optionally migrate, then run the API
#   migrate   run `alembic upgrade head` and exit — for a release/pre-deploy job
#   seed      load demo data and exit — NEVER run against production
#   <other>   exec'd verbatim, so `docker run kio-api sh` still works
#
set -eu

# -------------------------------------------------------------------
# Migrations
# -------------------------------------------------------------------
# Alembic reads DATABASE_URL through app.config (migrations/env.py overrides
# alembic.ini's sqlalchemy.url), so no extra wiring is needed here.
run_migrations() {
    echo "==> alembic upgrade head"
    alembic upgrade head
    echo "==> migrations complete"
}

case "${1:-serve}" in
    migrate)
        run_migrations
        ;;

    seed)
        # Guard rail: seeding creates demo accounts that all share one published
        # password. That must never happen in production.
        if [ "${ENVIRONMENT:-development}" = "production" ]; then
            echo "REFUSING to seed: ENVIRONMENT=production" >&2
            exit 1
        fi
        run_migrations
        echo "==> seeding demo data"
        python -m database.seed
        ;;

    serve)
        # Default on so a single-container deploy is correct out of the box.
        # Set RUN_MIGRATIONS=false when a separate release job owns the upgrade
        # (the right choice once you run more than one replica — concurrent
        # `alembic upgrade` from N starting containers can deadlock).
        if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
            run_migrations
        else
            echo "==> skipping migrations (RUN_MIGRATIONS=false)"
        fi

        # WEB_CONCURRENCY defaults to 1 deliberately. Two in-process subsystems
        # are not yet shared across workers:
        #   * app/rate_limit.py keeps counters in a per-process dict, so N
        #     workers means every limit is effectively N times looser.
        #   * the intelligence/crisis pipeline runs in FastAPI BackgroundTasks
        #     inside the worker that served the request.
        # Scale by raising this only after both move to a shared backing store;
        # until then scale vertically, or run more single-worker containers and
        # accept that rate limits are per-container.
        workers="${WEB_CONCURRENCY:-1}"
        echo "==> starting uvicorn on 0.0.0.0:${PORT:-8000} (workers=${workers})"

        # exec so uvicorn becomes PID 1 and receives SIGTERM directly —
        # without it, in-flight background tasks are killed rather than drained.
        exec uvicorn main:app \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --workers "$workers" \
            --proxy-headers \
            --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" \
            --timeout-graceful-shutdown "${GRACEFUL_TIMEOUT:-30}"
        ;;

    *)
        exec "$@"
        ;;
esac
