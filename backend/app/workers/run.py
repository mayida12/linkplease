"""
Entry point for the background worker process.

Run with:  python -m app.workers.run

Deliberately a single plain Python process with a simple loop instead of
Celery/RQ - see the README section "Why not Redis/Celery" for the reasoning.
Everything it needs to pick up where it left off (which events are
unprocessed, which jobs are due, which jobs need reconciling) lives in
Postgres, so if this process is killed and restarted, it just starts
polling again and continues exactly where the data says it should.

It is safe to run more than one copy of this process at once - all three
loops claim their work with `SELECT ... FOR UPDATE SKIP LOCKED`, so two
workers never grab the same event or the same job.
"""
import logging
import time

from app.config import settings
from app.database.session import SessionLocal
from app.workers import event_processor, dm_sender, reconciler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("worker")


def loop_forever():
    logger.info("worker started")
    while True:
        try:
            _run_all_passes()
        except Exception:
            # A bug or a DB hiccup in one pass shouldn't kill the whole
            # worker process - log it and try again next cycle. Any job or
            # event this iteration didn't finish stays exactly as it was in
            # the database, so nothing is lost.
            logger.exception("worker pass failed, will retry next cycle")

        time.sleep(settings.worker_poll_interval_seconds)


def _run_all_passes():
    with SessionLocal() as db:
        processed = event_processor.run_once(db)
        if processed:
            logger.info("processed %d webhook event(s)", processed)

    with SessionLocal() as db:
        sent = dm_sender.run_once(db)
        if sent:
            logger.info("attempted %d dm send(s)", sent)

    with SessionLocal() as db:
        checked = reconciler.run_once(db)
        if checked:
            logger.info("reconciled %d dm job(s)", checked)


if __name__ == "__main__":
    loop_forever()
