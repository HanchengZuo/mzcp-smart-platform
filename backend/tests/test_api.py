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

    first_template = client.post(
        "/api/templates",
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
    assert first_template.status_code == 201

    second_template = client.post(
        "/api/templates",
        json={
            "title": "补充问卷",
            "sections": [
                {
                    "title": "补充测评",
                    "items": [
                        {"title": "协同配合情况"},
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert second_template.status_code == 201

    task = client.post(
        "/api/forms",
        json={
            "template_ids": [
                first_template.get_json()["id"],
                second_template.get_json()["id"],
            ],
            "unit_id": unit.get_json()["id"],
            "group_id": group.get_json()["id"],
            "period_id": period.get_json()["id"],
        },
        headers=headers,
    )
    assert task.status_code == 201
    task_json = task.get_json()
    assert len(task_json["forms"]) == 2
    assert [form["form_order"] for form in task_json["forms"]] == [1, 2]
    assert task_json["forms"][0]["template_id"] == first_template.get_json()["id"]
    return unit.get_json(), group.get_json(), period.get_json(), task_json


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
    unit, group, _period, task = create_base_task(client, headers)
    first_form = task["forms"][0]
    second_form = task["forms"][1]
    level_id = client.get("/api/levels", headers=headers).get_json()["items"][0]["id"]

    group_headers = auth_headers(client, "group1", "pass123")
    link = client.post(
        f"/api/tasks/{task['id']}/links",
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
    assert len(survey_json["forms"]) == 2
    assert [form["title"] for form in survey_json["forms"]] == ["民主测评表", "补充问卷"]
    assert survey_json["forms"][0]["sections"][0]["title"] == "政治建设"

    first_form_json = survey_json["forms"][0]
    second_form_json = survey_json["forms"][1]
    first_option_id = first_form_json["options"][0]["id"]
    second_option_id = first_form_json["options"][1]["id"]
    third_option_id = second_form_json["options"][0]["id"]
    invalid_response = client.post(
        f"/api/public/surveys/{token}/responses",
        json={
            "answers": {
                str(first_form_json["items"][0]["id"]): first_option_id,
                str(first_form_json["items"][1]["id"]): second_option_id,
                str(first_form_json["items"][2]["id"]): "继续保持",
                str(second_form_json["items"][0]["id"]): first_option_id,
            }
        },
    )
    assert invalid_response.status_code == 400
    response = client.post(
        f"/api/public/surveys/{token}/responses",
        json={
            "answers": {
                str(first_form_json["items"][0]["id"]): first_option_id,
                str(first_form_json["items"][1]["id"]): second_option_id,
                str(first_form_json["items"][2]["id"]): "继续保持",
                str(second_form_json["items"][0]["id"]): third_option_id,
            }
        },
    )
    assert response.status_code == 201

    stats = client.get(f"/api/stats/forms/{first_form['id']}", headers=headers)
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
    second_stats = client.get(f"/api/stats/forms/{second_form['id']}", headers=headers)
    assert second_stats.status_code == 200
    assert second_stats.get_json()["overall"]["options"][0]["count"] == 1

    unit_delete = client.delete(f"/api/units/{unit['id']}", headers=headers)
    assert unit_delete.status_code == 400
    group_delete = client.delete(f"/api/groups/{group['id']}", headers=headers)
    assert group_delete.status_code == 400
    task_delete = client.delete(f"/api/tasks/{task['id']}", headers=headers)
    assert task_delete.status_code == 200
    assert client.get(f"/api/public/surveys/{token}").status_code == 404
    assert client.get(f"/api/stats/forms/{first_form['id']}", headers=headers).status_code == 404


def test_create_form_with_multiple_units():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET": "test-secret",
        }
    )
    client = app.test_client()
    headers = auth_headers(client)

    first_unit = client.post("/api/units", json={"name": "第一单位"}, headers=headers)
    second_unit = client.post("/api/units", json={"name": "第二单位"}, headers=headers)
    assert first_unit.status_code == 201
    assert second_unit.status_code == 201

    group = client.post(
        "/api/groups",
        json={"name": "第一巡察组", "username": "group1", "password": "pass123"},
        headers=headers,
    )
    period = client.post(
        "/api/periods",
        json={
            "name": "2026年下半年",
            "year": 2026,
            "half": "下半年",
            "starts_on": "2026-07-01",
            "ends_on": "2026-12-31",
        },
        headers=headers,
    )
    assert group.status_code == 201
    assert period.status_code == 201

    template = client.post(
        "/api/templates",
        json={
            "title": "同名民主测评表",
            "sections": [
                {
                    "title": "综合测评",
                    "items": [{"title": "履职情况"}],
                }
            ],
        },
        headers=headers,
    )
    assert template.status_code == 201

    response = client.post(
        "/api/forms",
        json={
            "template_ids": [template.get_json()["id"]],
            "unit_ids": [
                first_unit.get_json()["id"],
                second_unit.get_json()["id"],
            ],
            "group_id": group.get_json()["id"],
            "period_id": period.get_json()["id"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["created_count"] == 2
    assert len(payload["tasks"]) == 2
    assert {item["template_id"] for item in payload["items"]} == {
        template.get_json()["id"]
    }
    assert {item["unit_id"] for item in payload["items"]} == {
        first_unit.get_json()["id"],
        second_unit.get_json()["id"],
    }

    forms = client.get("/api/forms", headers=headers).get_json()["items"]
    assert len(forms) == 2
    assert {item["unit"]["name"] for item in forms} == {"第一单位", "第二单位"}
