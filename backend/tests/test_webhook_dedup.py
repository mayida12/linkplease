from app.models.dm_job import DmJob
from app.models.duplicate_block import DuplicateBlock
from app.models.webhook_event import WebhookEvent
from app.workers import event_processor
from tests.helpers import make_comment_event, post_event


def create_rule(client, keyword="PRICE", message="Here's the price list"):
    response = client.post("/rules", json={"keyword": keyword, "dm_message": message})
    return response.json()["rule_id"]


# --- Test 4: duplicate event_id ---------------------------------------------

def test_duplicate_event_id_is_only_stored_once(client, db):
    create_rule(client)
    event = make_comment_event("evt_dup_01", "PRICE please", user_id="usr_A")

    r1 = post_event(client, event)
    r2 = post_event(client, event)  # exact same event_id, sent again

    assert r1.status_code == 200
    assert r2.status_code == 200  # still acknowledged, per spec - just not reprocessed

    rows = db.query(WebhookEvent).filter(WebhookEvent.event_id == "evt_dup_01").all()
    assert len(rows) == 1


def test_duplicate_event_id_only_creates_one_dm_job(client, db):
    create_rule(client)
    event = make_comment_event("evt_dup_02", "PRICE please", user_id="usr_B")

    post_event(client, event)
    post_event(client, event)

    event_processor.run_once(db)
    event_processor.run_once(db)  # second pass should find nothing new to do

    jobs = db.query(DmJob).filter(DmJob.recipient_user_id == "usr_B").all()
    assert len(jobs) == 1


# --- Test 5: same user commenting multiple times ----------------------------

def test_same_user_multiple_matching_comments_only_gets_one_dm(client, db):
    create_rule(client, keyword="PRICE")

    post_event(client, make_comment_event("evt_1", "PRICE", user_id="usr_arjun", comment_id="c1"))
    post_event(client, make_comment_event("evt_2", "PRICE please", user_id="usr_arjun", comment_id="c2"))
    post_event(client, make_comment_event("evt_3", "Can I get the PRICE?", user_id="usr_arjun", comment_id="c3"))

    event_processor.run_once(db)

    jobs = db.query(DmJob).filter(DmJob.recipient_user_id == "usr_arjun").all()
    assert len(jobs) == 1

    blocks = db.query(DuplicateBlock).filter(DuplicateBlock.recipient_user_id == "usr_arjun").all()
    assert len(blocks) == 2  # the 2nd and 3rd comments were correctly blocked


# --- Test 6: different users matching the same rule -------------------------

def test_different_users_each_get_their_own_dm(client, db):
    create_rule(client, keyword="PRICE")

    post_event(client, make_comment_event("evt_a", "PRICE", user_id="usr_1", comment_id="ca"))
    post_event(client, make_comment_event("evt_b", "PRICE", user_id="usr_2", comment_id="cb"))
    post_event(client, make_comment_event("evt_c", "PRICE", user_id="usr_3", comment_id="cc"))

    event_processor.run_once(db)

    jobs = db.query(DmJob).all()
    recipients = {job.recipient_user_id for job in jobs}
    assert recipients == {"usr_1", "usr_2", "usr_3"}
    assert db.query(DuplicateBlock).count() == 0
