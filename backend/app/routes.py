from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO
from secrets import token_urlsafe

import jwt
import qrcode
from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import func
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, Unauthorized

from .extensions import db
from .models import (
    DEFAULT_FORM_OPTIONS,
    EvaluationForm,
    FormItem,
    FormOption,
    FormSection,
    InspectionGroup,
    PeriodTask,
    PersonLevel,
    SurveyAnswer,
    SurveyLink,
    SurveyResponse,
    Unit,
)

api = Blueprint("api", __name__)


def json_response(payload=None, status=200):
    return jsonify(payload or {}), status


def parse_json():
    return request.get_json(silent=True) or {}


def require_text(data, key):
    value = str(data.get(key, "")).strip()
    if not value:
        raise BadRequest(f"{key} is required")
    return value


def require_int(data, key):
    try:
        return int(data.get(key))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{key} is required") from exc


def parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on", "启用")


def parse_date(value, key):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{key} must be YYYY-MM-DD") from exc


def create_token(identity):
    now = datetime.utcnow()
    payload = {
        **identity,
        "iat": now,
        "exp": now + timedelta(hours=12),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def current_identity():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise Unauthorized("missing bearer token")
    token = header.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise Unauthorized("invalid token") from exc

    if payload.get("role") == "group":
        group = db.session.get(InspectionGroup, payload.get("group_id"))
        if not group or not group.enabled:
            raise Unauthorized("group account is disabled")
        payload["group"] = group
    return payload


def auth_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            identity = current_identity()
            if roles and identity.get("role") not in roles:
                raise Forbidden("permission denied")
            return fn(identity, *args, **kwargs)

        return wrapper

    return decorator


def get_form_or_404(form_id):
    form = db.session.get(EvaluationForm, form_id)
    if not form:
        raise NotFound("form not found")
    return form


def ensure_group_can_access_form(identity, form):
    if identity.get("role") == "root":
        return
    if form.group_id != identity["group"].id:
        raise Forbidden("permission denied")


def form_has_responses(form):
    return (
        SurveyResponse.query.join(SurveyLink)
        .filter(SurveyLink.form_id == form.id)
        .first()
        is not None
    )


def parse_unit_ids(data):
    raw_unit_ids = data.get("unit_ids")
    if raw_unit_ids is None:
        return [require_int(data, "unit_id")]
    if not isinstance(raw_unit_ids, list):
        raise BadRequest("请选择测评单位")

    unit_ids = []
    for raw_unit_id in raw_unit_ids:
        try:
            unit_id = int(raw_unit_id)
        except (TypeError, ValueError) as exc:
            raise BadRequest("请选择测评单位") from exc
        if unit_id not in unit_ids:
            unit_ids.append(unit_id)
    if not unit_ids:
        raise BadRequest("请至少选择一个测评单位")

    existing_ids = {
        unit.id for unit in Unit.query.filter(Unit.id.in_(unit_ids)).all()
    }
    if set(unit_ids) != existing_ids:
        raise NotFound("unit not found")
    return unit_ids


def build_form_from_data(data, unit_id):
    form = EvaluationForm(
        title=require_text(data, "title"),
        description=str(data.get("description", "")).strip(),
        status=str(data.get("status", "active")).strip() or "active",
        unit_id=unit_id,
        group_id=require_int(data, "group_id"),
        period_id=require_int(data, "period_id"),
    )
    apply_intro_settings(form, data)
    apply_form_structure(form, data)
    return form


def delete_form_with_related_data(form):
    item_ids = [
        item_id
        for (item_id,) in db.session.query(FormItem.id)
        .filter(FormItem.form_id == form.id)
        .all()
    ]
    if item_ids:
        SurveyAnswer.query.filter(SurveyAnswer.item_id.in_(item_ids)).delete(
            synchronize_session=False,
        )

    link_ids = [
        link_id
        for (link_id,) in db.session.query(SurveyLink.id)
        .filter(SurveyLink.form_id == form.id)
        .all()
    ]
    if link_ids:
        SurveyResponse.query.filter(SurveyResponse.link_id.in_(link_ids)).delete(
            synchronize_session=False,
        )
        SurveyLink.query.filter(SurveyLink.id.in_(link_ids)).delete(
            synchronize_session=False,
        )

    db.session.delete(form)


def normalize_options(raw_options):
    source = raw_options or DEFAULT_FORM_OPTIONS
    options = []
    seen_values = set()
    for index, raw_option in enumerate(source, start=1):
        if isinstance(raw_option, str):
            label = raw_option.strip()
            score_weight = 0
            value = f"option_{index}"
        else:
            label = str(raw_option.get("label", "")).strip()
            score_weight = int(raw_option.get("score_weight") or 0)
            value = str(raw_option.get("value") or f"option_{index}").strip()
        if not label:
            continue
        if value in seen_values:
            value = f"{value}_{index}"
        seen_values.add(value)
        options.append(
            {
                "label": label,
                "value": value,
                "score_weight": score_weight,
                "sort_order": index,
            }
        )
    if len(options) < 2:
        raise BadRequest("至少需要设置两个测评选项")
    return options


def normalize_sections(data):
    raw_sections = data.get("sections")
    if not raw_sections and data.get("items"):
        raw_sections = [{"title": "综合测评", "items": data.get("items")}]
    if not raw_sections:
        raw_sections = [{"title": "综合测评", "items": [""]}]

    sections = []
    for section_index, raw_section in enumerate(raw_sections, start=1):
        title = str(raw_section.get("title", "")).strip() or f"测评维度{section_index}"
        raw_items = raw_section.get("items") or []
        items = []
        for item_index, raw_item in enumerate(raw_items, start=1):
            if isinstance(raw_item, dict):
                item_title = str(raw_item.get("title", "")).strip()
                item_type = str(raw_item.get("item_type") or "choice").strip()
            else:
                item_title = str(raw_item).strip()
                item_type = "choice"
            if item_type not in ("choice", "text"):
                raise BadRequest("测评项类型不正确")
            if item_title:
                items.append(
                    {
                        "title": item_title,
                        "item_type": item_type,
                        "sort_order": item_index,
                    }
                )
        if items:
            sections.append(
                {
                    "title": title,
                    "sort_order": section_index,
                    "items": items,
                }
            )
    if not sections:
        raise BadRequest("至少需要设置一个测评维度和一个测评项")
    return sections


def apply_form_structure(form, data):
    form.options = [
        FormOption(**option) for option in normalize_options(data.get("options"))
    ]
    form.sections = []
    for section_data in normalize_sections(data):
        section = FormSection(
            title=section_data["title"],
            sort_order=section_data["sort_order"],
        )
        for item_data in section_data["items"]:
            section.items.append(FormItem(form=form, **item_data))
        form.sections.append(section)


def apply_intro_settings(form, data):
    form.show_intro = parse_bool(data.get("show_intro"), default=True)
    form.intro_text = str(
        data.get(
            "intro_text",
            "请认真阅读测评说明，客观、公正、独立完成本次民主测评。",
        )
    ).strip() or "请认真阅读测评说明，客观、公正、独立完成本次民主测评。"
    try:
        intro_seconds = int(data.get("intro_seconds") or 5)
    except (TypeError, ValueError) as exc:
        raise BadRequest("告知事项倒计时必须是数字") from exc
    form.intro_seconds = max(0, min(60, intro_seconds))


def distribution_for_items(form, item_ids, level_id=None):
    if not item_ids:
        return {
            "total": 0,
            "satisfaction_percent": 0,
            "options": [
                {
                    "option_id": option.id,
                    "label": option.label,
                    "score_weight": option.score_weight,
                    "count": 0,
                }
                for option in form.options
            ],
        }
    rows = (
        db.session.query(
            SurveyAnswer.option_id,
            SurveyAnswer.option_label,
            func.count(SurveyAnswer.id),
            func.coalesce(func.sum(SurveyAnswer.score_weight), 0),
        )
        .join(SurveyResponse)
        .join(SurveyLink)
        .filter(SurveyLink.form_id == form.id)
        .filter(SurveyAnswer.item_id.in_(item_ids))
        .filter(SurveyAnswer.option_id.isnot(None))
    )
    if level_id is not None:
        rows = rows.filter(SurveyLink.level_id == level_id)
    rows = rows.group_by(SurveyAnswer.option_id, SurveyAnswer.option_label).all()
    by_option = {
        option_id: {"count": count, "weighted_sum": weighted_sum}
        for option_id, _label, count, weighted_sum in rows
    }
    options = []
    total = 0
    weighted_total = 0
    max_weight = max([option.score_weight for option in form.options] or [0])
    for option in form.options:
        row = by_option.get(option.id, {"count": 0, "weighted_sum": 0})
        count = int(row["count"])
        weighted_sum = int(row["weighted_sum"])
        total += count
        weighted_total += weighted_sum
        options.append(
            {
                "option_id": option.id,
                "label": option.label,
                "score_weight": option.score_weight,
                "count": count,
            }
        )
    satisfaction_percent = (
        round(weighted_total / (total * max_weight) * 100, 2)
        if total and max_weight
        else 0
    )
    return {
        "total": total,
        "satisfaction_percent": satisfaction_percent,
        "options": options,
    }


def form_progress(form):
    links = [link.to_dict() for link in form.links]
    response_count = sum(link["response_count"] for link in links)
    target_count = sum(link["target_count"] for link in links)
    completion_percent = (
        round(response_count / target_count * 100, 2) if target_count else 0
    )
    return {
        "link_count": len(links),
        "target_count": target_count,
        "response_count": response_count,
        "completion_percent": completion_percent,
        "links": links,
    }


def section_stats_for_form(form, level_id=None):
    sections = []
    for section in form.sections:
        section_choice_item_ids = [
            item.id for item in section.items if item.item_type == "choice"
        ]
        sections.append(
            {
                "section_id": section.id,
                "title": section.title,
                "sort_order": section.sort_order,
                "summary": distribution_for_items(
                    form,
                    section_choice_item_ids,
                    level_id,
                ),
                "items": [
                    item_stats_payload(form, item, level_id)
                    for item in section.items
                ],
            }
        )
    return sections


def text_answers_for_item(form, item, level_id=None):
    query = (
        db.session.query(SurveyAnswer, SurveyResponse, SurveyLink)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
        .join(SurveyLink, SurveyResponse.link_id == SurveyLink.id)
        .filter(SurveyLink.form_id == form.id)
        .filter(SurveyAnswer.item_id == item.id)
        .filter(SurveyAnswer.text_value != "")
    )
    if level_id is not None:
        query = query.filter(SurveyLink.level_id == level_id)
    rows = query.order_by(SurveyResponse.submitted_at.desc()).all()
    return [
        {
            "answer_id": answer.id,
            "text": answer.text_value,
            "submitted_at": response.submitted_at.isoformat(),
            "level": link.level.to_dict() if link.level else None,
        }
        for answer, response, link in rows
    ]


def item_stats_payload(form, item, level_id=None):
    payload = {
        "item_id": item.id,
        "title": item.title,
        "item_type": item.item_type,
        "sort_order": item.sort_order,
    }
    if item.item_type == "text":
        payload["text_answers"] = text_answers_for_item(form, item, level_id)
        payload["text_count"] = len(payload["text_answers"])
        payload["summary"] = distribution_for_items(form, [], level_id)
    else:
        payload["summary"] = distribution_for_items(form, [item.id], level_id)
    return payload


def level_stats_for_form(form, all_item_ids):
    stats = []
    for link in sorted(form.links, key=lambda item: item.level.sort_order if item.level else 0):
        stats.append(
            {
                "level": link.level.to_dict() if link.level else None,
                "progress": link.to_dict(),
                "overall": distribution_for_items(form, all_item_ids, link.level_id),
                "sections": section_stats_for_form(form, link.level_id),
            }
        )
    return stats


def form_stats_payload(form):
    all_item_ids = [item.id for item in form.items if item.item_type == "choice"]
    return {
        "form": form.to_dict(include_structure=False),
        "options": [option.to_dict() for option in form.options],
        "overall": distribution_for_items(form, all_item_ids),
        "progress": form_progress(form),
        "sections": section_stats_for_form(form),
        "levels": level_stats_for_form(form, all_item_ids),
    }


@api.errorhandler(BadRequest)
@api.errorhandler(Unauthorized)
@api.errorhandler(Forbidden)
@api.errorhandler(NotFound)
def handle_http_error(error):
    return json_response({"message": error.description}, error.code)


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/auth/login")
def login():
    data = parse_json()
    username = require_text(data, "username")
    password = require_text(data, "password")

    if (
        username == current_app.config["ROOT_USERNAME"]
        and password == current_app.config["ROOT_PASSWORD"]
    ):
        user = {"role": "root", "username": username, "name": "系统管理员"}
        return {"token": create_token(user), "user": user}

    group = InspectionGroup.query.filter_by(username=username).first()
    if not group or not group.enabled or not group.check_password(password):
        raise Unauthorized("账号或密码不正确")

    user = {
        "role": "group",
        "username": group.username,
        "name": group.name,
        "group_id": group.id,
    }
    return {"token": create_token(user), "user": user}


@api.get("/auth/me")
@auth_required("root", "group")
def me(identity):
    user = {
        "role": identity["role"],
        "username": identity["username"],
        "name": identity.get("name", identity["username"]),
    }
    if identity["role"] == "group":
        user["group_id"] = identity["group"].id
        user["name"] = identity["group"].name
    return {"user": user}


@api.get("/units")
@auth_required("root")
def list_units(_identity):
    units = Unit.query.order_by(Unit.created_at.desc()).all()
    return {"items": [unit.to_dict() for unit in units]}


@api.post("/units")
@auth_required("root")
def create_unit(_identity):
    unit = Unit(name=require_text(parse_json(), "name"))
    db.session.add(unit)
    db.session.commit()
    return unit.to_dict(), 201


@api.put("/units/<int:unit_id>")
@auth_required("root")
def update_unit(_identity, unit_id):
    unit = db.session.get(Unit, unit_id)
    if not unit:
        raise NotFound("unit not found")
    unit.name = require_text(parse_json(), "name")
    db.session.commit()
    return unit.to_dict()


@api.delete("/units/<int:unit_id>")
@auth_required("root")
def delete_unit(_identity, unit_id):
    unit = db.session.get(Unit, unit_id)
    if not unit:
        raise NotFound("unit not found")
    if unit.forms:
        raise BadRequest("该单位已经挂载测评表，不能删除")
    db.session.delete(unit)
    db.session.commit()
    return {"ok": True}


@api.get("/levels")
@auth_required("root", "group")
def list_levels(_identity):
    levels = PersonLevel.query.order_by(PersonLevel.sort_order, PersonLevel.id).all()
    return {"items": [level.to_dict() for level in levels]}


@api.post("/levels")
@auth_required("root")
def create_level(_identity):
    data = parse_json()
    max_order = db.session.query(func.coalesce(func.max(PersonLevel.sort_order), 0)).scalar()
    level = PersonLevel(
        name=require_text(data, "name"),
        description=str(data.get("description", "")).strip(),
        sort_order=max_order + 1,
    )
    db.session.add(level)
    db.session.commit()
    return level.to_dict(), 201


@api.put("/levels/reorder")
@auth_required("root")
def reorder_levels(_identity):
    data = parse_json()
    ids = data.get("ids") or []
    if not isinstance(ids, list):
        raise BadRequest("ids must be a list")
    levels = {level.id: level for level in PersonLevel.query.all()}
    if set(map(int, ids)) != set(levels.keys()):
        raise BadRequest("层级列表不完整")
    for index, level_id in enumerate(ids, start=1):
        levels[int(level_id)].sort_order = index
    db.session.commit()
    return {"items": [level.to_dict() for level in sorted(levels.values(), key=lambda item: item.sort_order)]}


@api.put("/levels/<int:level_id>")
@auth_required("root")
def update_level(_identity, level_id):
    level = db.session.get(PersonLevel, level_id)
    if not level:
        raise NotFound("level not found")
    data = parse_json()
    level.name = require_text(data, "name")
    level.description = str(data.get("description", "")).strip()
    db.session.commit()
    return level.to_dict()


@api.delete("/levels/<int:level_id>")
@auth_required("root")
def delete_level(_identity, level_id):
    level = db.session.get(PersonLevel, level_id)
    if not level:
        raise NotFound("level not found")
    if level.links:
        raise BadRequest("该测评人员层级已经生成二维码，不能删除")
    db.session.delete(level)
    db.session.commit()
    return {"ok": True}


@api.get("/groups")
@auth_required("root")
def list_groups(_identity):
    groups = InspectionGroup.query.order_by(InspectionGroup.created_at.desc()).all()
    return {"items": [group.to_dict(include_password=True) for group in groups]}


@api.post("/groups")
@auth_required("root")
def create_group(_identity):
    data = parse_json()
    group = InspectionGroup(
        name=require_text(data, "name"),
        username=require_text(data, "username"),
        enabled=parse_bool(data.get("enabled"), default=True),
    )
    group.set_password(require_text(data, "password"))
    db.session.add(group)
    db.session.commit()
    return group.to_dict(include_password=True), 201


@api.put("/groups/<int:group_id>")
@auth_required("root")
def update_group(_identity, group_id):
    group = db.session.get(InspectionGroup, group_id)
    if not group:
        raise NotFound("group not found")
    data = parse_json()
    group.name = require_text(data, "name")
    group.username = require_text(data, "username")
    group.enabled = parse_bool(data.get("enabled"), default=True)
    password = str(data.get("password", "")).strip()
    if password:
        group.set_password(password)
    db.session.commit()
    return group.to_dict(include_password=True)


@api.delete("/groups/<int:group_id>")
@auth_required("root")
def delete_group(_identity, group_id):
    group = db.session.get(InspectionGroup, group_id)
    if not group:
        raise NotFound("group not found")
    if group.forms:
        raise BadRequest("该巡察组账号已经分配测评任务，不能删除")
    db.session.delete(group)
    db.session.commit()
    return {"ok": True}


@api.get("/periods")
@auth_required("root", "group")
def list_periods(_identity):
    periods = PeriodTask.query.order_by(PeriodTask.year.desc(), PeriodTask.id.desc()).all()
    return {"items": [period.to_dict() for period in periods]}


@api.post("/periods")
@auth_required("root")
def create_period(_identity):
    data = parse_json()
    starts_on = parse_date(data.get("starts_on"), "starts_on")
    ends_on = parse_date(data.get("ends_on"), "ends_on")
    if starts_on > ends_on:
        raise BadRequest("starts_on must be before ends_on")
    period = PeriodTask(
        name=require_text(data, "name"),
        year=int(data.get("year") or starts_on.year),
        half=require_text(data, "half"),
        starts_on=starts_on,
        ends_on=ends_on,
    )
    db.session.add(period)
    db.session.commit()
    return period.to_dict(), 201


@api.put("/periods/<int:period_id>")
@auth_required("root")
def update_period(_identity, period_id):
    period = db.session.get(PeriodTask, period_id)
    if not period:
        raise NotFound("period not found")
    data = parse_json()
    starts_on = parse_date(data.get("starts_on"), "starts_on")
    ends_on = parse_date(data.get("ends_on"), "ends_on")
    if starts_on > ends_on:
        raise BadRequest("starts_on must be before ends_on")
    period.name = require_text(data, "name")
    period.year = int(data.get("year") or starts_on.year)
    period.half = require_text(data, "half")
    period.starts_on = starts_on
    period.ends_on = ends_on
    db.session.commit()
    return period.to_dict()


@api.delete("/periods/<int:period_id>")
@auth_required("root")
def delete_period(_identity, period_id):
    period = db.session.get(PeriodTask, period_id)
    if not period:
        raise NotFound("period not found")
    if period.forms:
        raise BadRequest("该时间任务已经挂载测评表，不能删除")
    db.session.delete(period)
    db.session.commit()
    return {"ok": True}


@api.get("/forms")
@auth_required("root", "group")
def list_forms(identity):
    query = EvaluationForm.query
    if identity["role"] == "group":
        query = query.filter_by(group_id=identity["group"].id)
    forms = query.order_by(EvaluationForm.created_at.desc()).all()
    return {
        "items": [
            {
                **form.to_dict(include_structure=False),
                "progress": form_progress(form),
            }
            for form in forms
        ]
    }


@api.post("/forms")
@auth_required("root")
def create_form(_identity):
    data = parse_json()
    forms = [build_form_from_data(data, unit_id) for unit_id in parse_unit_ids(data)]
    db.session.add_all(forms)
    db.session.commit()
    if len(forms) == 1:
        return forms[0].to_dict(), 201
    return {
        "created_count": len(forms),
        "items": [form.to_dict() for form in forms],
    }, 201


@api.get("/forms/<int:form_id>")
@auth_required("root", "group")
def get_form(identity, form_id):
    form = get_form_or_404(form_id)
    ensure_group_can_access_form(identity, form)
    return {
        **form.to_dict(),
        "progress": form_progress(form),
    }


@api.put("/forms/<int:form_id>")
@auth_required("root")
def update_form(_identity, form_id):
    form = get_form_or_404(form_id)
    if form_has_responses(form):
        raise BadRequest("已有答卷的测评表不能修改表单结构")
    data = parse_json()
    form.title = require_text(data, "title")
    form.description = str(data.get("description", "")).strip()
    form.status = str(data.get("status", "active")).strip() or "active"
    form.unit_id = require_int(data, "unit_id")
    form.group_id = require_int(data, "group_id")
    form.period_id = require_int(data, "period_id")
    apply_intro_settings(form, data)
    apply_form_structure(form, data)
    db.session.commit()
    return form.to_dict()


@api.delete("/forms/<int:form_id>")
@auth_required("root")
def delete_form(_identity, form_id):
    form = get_form_or_404(form_id)
    delete_form_with_related_data(form)
    db.session.commit()
    return {"ok": True}


@api.get("/forms/<int:form_id>/links")
@auth_required("root", "group")
def list_links(identity, form_id):
    form = get_form_or_404(form_id)
    ensure_group_can_access_form(identity, form)
    return {"items": [link.to_dict() for link in form.links]}


@api.post("/forms/<int:form_id>/links")
@auth_required("root", "group")
def create_link(identity, form_id):
    form = get_form_or_404(form_id)
    ensure_group_can_access_form(identity, form)
    data = parse_json()
    level = db.session.get(PersonLevel, require_int(data, "level_id"))
    if not level:
        raise NotFound("level not found")
    link = SurveyLink.query.filter_by(form_id=form.id, level_id=level.id).first()
    if not link:
        link = SurveyLink(form=form, level=level, token=token_urlsafe(24))
        db.session.add(link)
    link.target_count = max(0, int(data.get("target_count") or link.target_count or 0))
    link.active = True
    db.session.commit()
    return link.to_dict(), 201


@api.put("/links/<int:link_id>")
@auth_required("root", "group")
def update_link(identity, link_id):
    link = db.session.get(SurveyLink, link_id)
    if not link:
        raise NotFound("link not found")
    ensure_group_can_access_form(identity, link.form)
    data = parse_json()
    link.target_count = max(0, int(data.get("target_count") or 0))
    link.active = parse_bool(data.get("active"), default=True)
    db.session.commit()
    return link.to_dict()


@api.get("/public/surveys/<token>")
def get_public_survey(token):
    link = SurveyLink.query.filter_by(token=token, active=True).first()
    if not link:
        raise NotFound("survey not found")
    form = link.form
    today = date.today()
    is_open = (
        form.status == "active"
        and form.period.starts_on <= today <= form.period.ends_on
    )
    payload = form.to_dict()
    payload["level"] = link.level.to_dict()
    payload["token"] = link.token
    payload["is_open"] = is_open
    payload["score_options"] = [option.to_dict() for option in form.options]
    return payload


@api.post("/public/surveys/<token>/responses")
def submit_public_survey(token):
    link = SurveyLink.query.filter_by(token=token, active=True).first()
    if not link:
        raise NotFound("survey not found")
    form = link.form
    today = date.today()
    if form.status != "active" or today < form.period.starts_on or today > form.period.ends_on:
        raise BadRequest("测评表不在填报时间内")

    data = parse_json()
    answers = data.get("answers") or {}
    if not isinstance(answers, dict):
        raise BadRequest("请完成所有题项")
    item_ids = {item.id for item in form.items}
    try:
        answered_item_ids = {int(item_id) for item_id in answers.keys()}
    except (TypeError, ValueError) as exc:
        raise BadRequest("请完成所有题项") from exc
    if answered_item_ids != item_ids:
        raise BadRequest("请完成所有题项")

    option_by_id = {option.id: option for option in form.options}
    response = SurveyResponse(
        link=link,
        respondent_note=str(data.get("respondent_note", "")).strip(),
    )
    for item in form.items:
        answer_value = answers.get(str(item.id)) or answers.get(item.id)
        if item.item_type == "text":
            text_value = str(answer_value or "").strip()
            if not text_value:
                raise BadRequest("请完成所有问答题")
            response.answers.append(SurveyAnswer(item=item, text_value=text_value))
        else:
            try:
                option_id = int(answer_value)
            except (TypeError, ValueError) as exc:
                raise BadRequest("评分选项不正确") from exc
            option = option_by_id.get(option_id)
            if not option:
                raise BadRequest("评分选项不正确")
            response.answers.append(
                SurveyAnswer(
                    item=item,
                    option=option,
                    option_label=option.label,
                    score_weight=option.score_weight,
                )
            )
    db.session.add(response)
    db.session.commit()
    return {"ok": True, "response_id": response.id}, 201


@api.get("/public/links/<token>/qr")
def qr_code(token):
    link = SurveyLink.query.filter_by(token=token, active=True).first()
    if not link:
        raise NotFound("survey not found")
    frontend_origin = request.args.get("origin") or request.host_url.rstrip("/")
    survey_url = f"{frontend_origin}/#/survey/{link.token}"
    image = qrcode.make(survey_url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@api.get("/stats/forms/<int:form_id>")
@auth_required("root", "group")
def form_stats(identity, form_id):
    form = get_form_or_404(form_id)
    ensure_group_can_access_form(identity, form)
    return form_stats_payload(form)


@api.get("/stats/overview")
@auth_required("root", "group")
def stats_overview(identity):
    query = EvaluationForm.query
    if identity["role"] == "group":
        query = query.filter_by(group_id=identity["group"].id)
    forms = query.order_by(EvaluationForm.created_at.desc()).all()
    return {
        "items": [
            {
                **form.to_dict(include_structure=False),
                "progress": form_progress(form),
                "satisfaction_percent": form_stats_payload(form)["overall"][
                    "satisfaction_percent"
                ],
            }
            for form in forms
        ]
    }


@api.get("/tasks/progress")
@auth_required("root", "group")
def task_progress(identity):
    query = EvaluationForm.query
    if identity["role"] == "group":
        query = query.filter_by(group_id=identity["group"].id)
    forms = query.order_by(EvaluationForm.created_at.desc()).all()
    return {
        "items": [
            {
                "form": form.to_dict(include_structure=False),
                "progress": form_progress(form),
            }
            for form in forms
        ]
    }
