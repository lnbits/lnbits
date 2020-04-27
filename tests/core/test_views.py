def test_homepage(client):
    r = client.get("/")
    assert b"Add a new wallet" in r.data
