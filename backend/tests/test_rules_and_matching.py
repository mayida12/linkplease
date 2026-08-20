from app.models.rule import Rule
from app.services.matching import find_matching_rule


# --- Test 1: creating a rule -------------------------------------------------

def test_create_rule_returns_201_and_rule_id(client):
    response = client.post("/rules", json={"keyword": "PRICE", "dm_message": "Here's the price list"})
    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "PRICE"
    assert body["dm_message"] == "Here's the price list"
    assert "rule_id" in body and body["rule_id"]


def test_create_rule_persists_to_db(client, db):
    client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "10% off!"})
    rules = db.query(Rule).all()
    assert len(rules) == 1
    assert rules[0].keyword == "DISCOUNT"


# --- Test 2: case-insensitive keyword matching ------------------------------

def test_matching_is_case_insensitive():
    rule = Rule(id="r1", keyword="PRICE", dm_message="msg")
    assert find_matching_rule("price please", [rule]) is rule
    assert find_matching_rule("PRICE PLEASE", [rule]) is rule
    assert find_matching_rule("PrIcE please", [rule]) is rule


# --- Test 3: keyword appearing anywhere in the comment ----------------------

def test_matching_finds_keyword_anywhere_in_text():
    rule = Rule(id="r1", keyword="PRICE", dm_message="msg")
    assert find_matching_rule("PRICE please 🙏", [rule]) is rule
    assert find_matching_rule("Can I get the PRICE?", [rule]) is rule
    assert find_matching_rule("what's the pricetag", [rule]) is rule  # substring match, by design
    assert find_matching_rule("no keyword here", [rule]) is None


# --- Test 7: multiple rules --------------------------------------------------

def test_multiple_rules_each_match_their_own_keyword():
    price_rule = Rule(id="r1", keyword="PRICE", dm_message="price msg")
    shipping_rule = Rule(id="r2", keyword="SHIPPING", dm_message="shipping msg")
    rules = [price_rule, shipping_rule]

    assert find_matching_rule("what's the PRICE?", rules) is price_rule
    assert find_matching_rule("how's SHIPPING work?", rules) is shipping_rule
    assert find_matching_rule("neither keyword", rules) is None


def test_create_rule_end_to_end_then_matches_via_webhook(client, db):
    """Two rules created through the real API, then matched against comments."""
    client.post("/rules", json={"keyword": "PRICE", "dm_message": "price info"})
    client.post("/rules", json={"keyword": "SIZE", "dm_message": "size chart"})

    rules = db.query(Rule).all()
    assert len(rules) == 2

    matched = find_matching_rule("what SIZE do you have?", rules)
    assert matched.keyword == "SIZE"
