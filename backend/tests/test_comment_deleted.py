from app.models.dm_job import DmJob, PENDING
from app.workers import event_processor
from tests.helpers import make_comment_event, post_event


def test_comment_deleted_cancels_a_still_pending_dm_job(client, db):
    client.post("/rules", json={"keyword": "PRICE", "dm_message": "price info"})

    post_event(
        client,
        make_comment_event("evt_del_1", "PRICE please", user_id="usr_del", comment_id="cmt_del_1"),
    )
    event_processor.run_once(db)

    job = db.query(DmJob).filter(DmJob.recipient_user_id == "usr_del").one()
    assert job.status == PENDING

    post_event(
        client,
        make_comment_event(
            "evt_del_2",
            text="",
            user_id="usr_del",
            comment_id="cmt_del_1",
            event_type="comment.deleted",
        ),
    )
    event_processor.run_once(db)

    db.refresh(job)
    assert job.status == "cancelled"


def test_comment_deleted_for_unknown_comment_is_a_no_op(client, db):
    post_event(
        client,
        make_comment_event(
            "evt_del_unknown", text="", user_id="usr_x", comment_id="cmt_never_seen",
            event_type="comment.deleted",
        ),
    )
    # Should not raise, and should mark itself processed.
    handled = event_processor.run_once(db)
    assert handled == 1
