from app import create_app


def auth_headers(client, username="root", password="root123"):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_base_task(client, headers):
    unit = client.post("/api/units", json={"name": "测试单位"}, headers=headers)
    assert unit.status_code == 201

    group = client.post(
        "/api/groups",
        json={"name": "第一巡察组", "username": "group1", "password": "pass123"},
        headers=headers,
    )
    assert group.status_code == 201

    period = client.post(
        "/api/periods",
        json={
            "name": "2026年上半年",
            "year": 2026,
            "half": "上半年",
            "starts_on": "2000-01-01",
            "ends_on": "2999-12-31",
        },
        headers=headers,
    )
    assert period.status_code == 201

    form = client.post(
        "/api/forms",
        json={
            "title": "民主测评表",
            "show_intro": True,
            "intro_text": "请阅读后开始测评",
            "intro_seconds": 3,
            "unit_id": unit.get_json()["id"],
            "group_id": group.get_json()["id"],
            "period_id": period.get_json()["id"],
            "options": [
                {"label": "满意", "score_weight": 100},
                {"label": "基本满意", "score_weight": 60},
                {"label": "不满意", "score_weight": 0},
            ],
            "sections": [
                {
                    "title": "政治建设",
                    "items": [
                        {"title": "学习贯彻习近平新时代中国特色社会主义思想"},
                        {"title": "落实公司党委重大部署情况"},
                        {"title": "请填写对本单位的意见建议", "item_type": "text"},
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert form.status_code == 201
    return unit.get_json(), group.get_json(), period.get_json(), form.get_json()


def test_root_to_public_survey_flow():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET": "test-secret",
        }
    )
    client = app.test_client()
    headers = auth_headers(client)
    unit, group, _period, form = create_base_task(client, headers)
    level_id = client.get("/api/levels", headers=headers).get_json()["items"][0]["id"]

    group_headers = auth_headers(client, "group1", "pass123")
    link = client.post(
        f"/api/forms/{form['id']}/links",
        json={"level_id": level_id, "target_count": 2},
        headers=group_headers,
    )
    assert link.status_code == 201
    token = link.get_json()["token"]

    survey = client.get(f"/api/public/surveys/{token}")
    assert survey.status_code == 200
    survey_json = survey.get_json()
    assert survey_json["is_open"] is True
    assert survey_json["show_intro"] is True
    assert survey_json["intro_seconds"] == 3
    assert survey_json["sections"][0]["title"] == "政治建设"

    first_option_id = survey_json["options"][0]["id"]
    second_option_id = survey_json["options"][1]["id"]
    response = client.post(
        f"/api/public/surveys/{token}/responses",
        json={
            "answers": {
                str(survey_json["items"][0]["id"]): first_option_id,
                str(survey_json["items"][1]["id"]): second_option_id,
                str(survey_json["items"][2]["id"]): "继续保持",
            }
        },
    )
    assert response.status_code == 201

    stats = client.get(f"/api/stats/forms/{form['id']}", headers=headers)
    assert stats.status_code == 200
    stats_json = stats.get_json()
    assert stats_json["progress"]["response_count"] == 1
    assert stats_json["progress"]["target_count"] == 2
    assert stats_json["sections"][0]["summary"]["options"][0]["count"] == 1
    assert stats_json["sections"][0]["items"][0]["summary"]["options"][0]["count"] == 1
    assert stats_json["sections"][0]["items"][2]["item_type"] == "text"
    assert stats_json["sections"][0]["items"][2]["text_count"] == 1
    assert stats_json["sections"][0]["items"][2]["text_answers"][0]["text"] == "继续保持"
    assert stats_json["levels"][0]["level"]["id"] == level_id
    assert stats_json["levels"][0]["progress"]["response_count"] == 1
    assert stats_json["levels"][0]["overall"]["options"][0]["count"] == 1

    unit_delete = client.delete(f"/api/units/{unit['id']}", headers=headers)
    assert unit_delete.status_code == 400
    group_delete = client.delete(f"/api/groups/{group['id']}", headers=headers)
    assert group_delete.status_code == 400
    form_delete = client.delete(f"/api/forms/{form['id']}", headers=headers)
    assert form_delete.status_code == 400
