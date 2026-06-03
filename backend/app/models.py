from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


DEFAULT_FORM_OPTIONS = [
    {"label": "满意", "value": "satisfied", "score_weight": 100},
    {"label": "基本满意", "value": "basic", "score_weight": 60},
    {"label": "不满意", "value": "unsatisfied", "score_weight": 0},
]


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Unit(TimestampMixin, db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    forms = db.relationship("EvaluationForm", back_populates="unit")
    tasks = db.relationship("EvaluationTask", back_populates="unit")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "form_count": len(self.forms),
        }


class PersonLevel(TimestampMixin, db.Model):
    __tablename__ = "person_levels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(240), nullable=False, default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    links = db.relationship("SurveyLink", back_populates="level")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sort_order": self.sort_order,
            "link_count": len(self.links),
        }


class InspectionGroup(TimestampMixin, db.Model):
    __tablename__ = "inspection_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    password_plain = db.Column(db.String(120), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    forms = db.relationship("EvaluationForm", back_populates="group")
    tasks = db.relationship("EvaluationTask", back_populates="group")

    def set_password(self, password):
        self.password_plain = password
        self.password_hash = generate_password_hash(
            password,
            method="pbkdf2:sha256",
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_password=True):
        payload = {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "enabled": self.enabled,
            "form_count": len(self.forms),
        }
        if include_password:
            payload["password"] = self.password_plain
        return payload


class PeriodTask(TimestampMixin, db.Model):
    __tablename__ = "period_tasks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    half = db.Column(db.String(20), nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)

    forms = db.relationship("EvaluationForm", back_populates="period")
    tasks = db.relationship("EvaluationTask", back_populates="period")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "year": self.year,
            "half": self.half,
            "starts_on": self.starts_on.isoformat(),
            "ends_on": self.ends_on.isoformat(),
            "form_count": len(self.forms),
        }


class FormTemplate(TimestampMixin, db.Model):
    __tablename__ = "form_templates"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    show_intro = db.Column(db.Boolean, nullable=False, default=True)
    intro_text = db.Column(
        db.Text,
        nullable=False,
        default="请认真阅读测评说明，客观、公正、独立完成本次民主测评。",
    )
    intro_seconds = db.Column(db.Integer, nullable=False, default=5)

    tasks = db.relationship("EvaluationForm", back_populates="template")
    options = db.relationship(
        "TemplateOption",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateOption.sort_order",
    )
    sections = db.relationship(
        "TemplateSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateSection.sort_order",
    )
    items = db.relationship(
        "TemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateItem.sort_order",
    )

    def to_dict(self, include_structure=True):
        payload = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "show_intro": self.show_intro,
            "intro_text": self.intro_text,
            "intro_seconds": self.intro_seconds,
            "task_count": len(self.tasks),
        }
        if include_structure:
            payload["options"] = [option.to_dict() for option in self.options]
            payload["sections"] = [section.to_dict() for section in self.sections]
            payload["items"] = [item.to_dict() for item in self.items]
        return payload


class EvaluationTask(TimestampMixin, db.Model):
    __tablename__ = "evaluation_tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    unit_id = db.Column(
        db.Integer,
        db.ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection_groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_id = db.Column(
        db.Integer,
        db.ForeignKey("period_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )

    unit = db.relationship("Unit", back_populates="tasks")
    group = db.relationship("InspectionGroup", back_populates="tasks")
    period = db.relationship("PeriodTask", back_populates="tasks")
    forms = db.relationship(
        "EvaluationForm",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="EvaluationForm.form_order",
    )
    links = db.relationship(
        "SurveyLink",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_forms=True):
        payload = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "unit_id": self.unit_id,
            "group_id": self.group_id,
            "period_id": self.period_id,
            "unit": self.unit.to_dict() if self.unit else None,
            "group": self.group.to_dict(include_password=False) if self.group else None,
            "period": self.period.to_dict() if self.period else None,
            "form_count": len(self.forms),
        }
        if include_forms:
            payload["forms"] = [
                form.to_dict(include_structure=False)
                for form in self.forms
            ]
        return payload


class EvaluationForm(TimestampMixin, db.Model):
    __tablename__ = "evaluation_forms"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("form_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_tasks.id", ondelete="CASCADE"),
        nullable=True,
    )
    form_order = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="active")
    show_intro = db.Column(db.Boolean, nullable=False, default=True)
    intro_text = db.Column(
        db.Text,
        nullable=False,
        default="请认真阅读测评说明，客观、公正、独立完成本次民主测评。",
    )
    intro_seconds = db.Column(db.Integer, nullable=False, default=5)
    unit_id = db.Column(
        db.Integer,
        db.ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection_groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_id = db.Column(
        db.Integer,
        db.ForeignKey("period_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )

    template = db.relationship("FormTemplate", back_populates="tasks")
    task = db.relationship("EvaluationTask", back_populates="forms")
    unit = db.relationship("Unit", back_populates="forms")
    group = db.relationship("InspectionGroup", back_populates="forms")
    period = db.relationship("PeriodTask", back_populates="forms")
    options = db.relationship(
        "FormOption",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormOption.sort_order",
    )
    sections = db.relationship(
        "FormSection",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormSection.sort_order",
    )
    items = db.relationship(
        "FormItem",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormItem.sort_order",
    )
    links = db.relationship(
        "SurveyLink",
        back_populates="form",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_structure=True):
        payload = {
            "id": self.id,
            "template_id": self.template_id,
            "task_id": self.task_id,
            "form_order": self.form_order,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "show_intro": self.show_intro,
            "intro_text": self.intro_text,
            "intro_seconds": self.intro_seconds,
            "unit_id": self.unit_id,
            "group_id": self.group_id,
            "period_id": self.period_id,
            "unit": self.unit.to_dict() if self.unit else None,
            "group": self.group.to_dict(include_password=False) if self.group else None,
            "period": self.period.to_dict() if self.period else None,
            "template": (
                self.template.to_dict(include_structure=False)
                if self.template
                else None
            ),
            "task": self.task.to_dict(include_forms=False) if self.task else None,
        }
        if include_structure:
            payload["options"] = [option.to_dict() for option in self.options]
            payload["sections"] = [section.to_dict() for section in self.sections]
            payload["items"] = [item.to_dict() for item in self.items]
        return payload


class TemplateOption(TimestampMixin, db.Model):
    __tablename__ = "template_options"
    __table_args__ = (
        db.UniqueConstraint("template_id", "value", name="uq_template_option_value"),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("form_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    label = db.Column(db.String(80), nullable=False)
    value = db.Column(db.String(80), nullable=False)
    score_weight = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    template = db.relationship("FormTemplate", back_populates="options")

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "score_weight": self.score_weight,
            "sort_order": self.sort_order,
        }


class FormOption(TimestampMixin, db.Model):
    __tablename__ = "form_options"
    __table_args__ = (
        db.UniqueConstraint("form_id", "value", name="uq_form_option_value"),
    )

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    label = db.Column(db.String(80), nullable=False)
    value = db.Column(db.String(80), nullable=False)
    score_weight = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    form = db.relationship("EvaluationForm", back_populates="options")
    answers = db.relationship("SurveyAnswer", back_populates="option")

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "score_weight": self.score_weight,
            "sort_order": self.sort_order,
        }


class TemplateSection(TimestampMixin, db.Model):
    __tablename__ = "template_sections"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("form_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(160), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    template = db.relationship("FormTemplate", back_populates="sections")
    items = db.relationship(
        "TemplateItem",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="TemplateItem.sort_order",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "sort_order": self.sort_order,
            "items": [item.to_dict(include_section=False) for item in self.items],
        }


class FormSection(TimestampMixin, db.Model):
    __tablename__ = "form_sections"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(160), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    form = db.relationship("EvaluationForm", back_populates="sections")
    items = db.relationship(
        "FormItem",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="FormItem.sort_order",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "sort_order": self.sort_order,
            "items": [item.to_dict(include_section=False) for item in self.items],
        }


class TemplateItem(TimestampMixin, db.Model):
    __tablename__ = "template_items"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("form_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id = db.Column(
        db.Integer,
        db.ForeignKey("template_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(240), nullable=False)
    item_type = db.Column(db.String(20), nullable=False, default="choice")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    template = db.relationship("FormTemplate", back_populates="items")
    section = db.relationship("TemplateSection", back_populates="items")

    def to_dict(self, include_section=True):
        payload = {
            "id": self.id,
            "section_id": self.section_id,
            "title": self.title,
            "item_type": self.item_type,
            "sort_order": self.sort_order,
        }
        if include_section:
            payload["section"] = (
                {
                    "id": self.section.id,
                    "title": self.section.title,
                    "sort_order": self.section.sort_order,
                }
                if self.section
                else None
            )
        return payload


class FormItem(TimestampMixin, db.Model):
    __tablename__ = "form_items"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id = db.Column(
        db.Integer,
        db.ForeignKey("form_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(240), nullable=False)
    item_type = db.Column(db.String(20), nullable=False, default="choice")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    form = db.relationship("EvaluationForm", back_populates="items")
    section = db.relationship("FormSection", back_populates="items")
    answers = db.relationship("SurveyAnswer", back_populates="item")

    def to_dict(self, include_section=True):
        payload = {
            "id": self.id,
            "section_id": self.section_id,
            "title": self.title,
            "item_type": self.item_type,
            "sort_order": self.sort_order,
        }
        if include_section:
            payload["section"] = (
                {
                    "id": self.section.id,
                    "title": self.section.title,
                    "sort_order": self.section.sort_order,
                }
                if self.section
                else None
            )
        return payload


class SurveyLink(TimestampMixin, db.Model):
    __tablename__ = "survey_links"
    __table_args__ = (
        db.UniqueConstraint("form_id", "level_id", name="uq_form_level"),
        db.UniqueConstraint("task_id", "level_id", name="uq_task_level"),
    )

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    form_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("evaluation_tasks.id", ondelete="CASCADE"),
        nullable=True,
    )
    level_id = db.Column(
        db.Integer,
        db.ForeignKey("person_levels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_count = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)

    form = db.relationship("EvaluationForm", back_populates="links")
    task = db.relationship("EvaluationTask", back_populates="links")
    level = db.relationship("PersonLevel", back_populates="links")
    responses = db.relationship(
        "SurveyResponse",
        back_populates="link",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        response_count = len(self.responses)
        completion_percent = (
            round(response_count / self.target_count * 100, 2)
            if self.target_count
            else 0
        )
        return {
            "id": self.id,
            "token": self.token,
            "form_id": self.form_id,
            "task_id": self.task_id,
            "level_id": self.level_id,
            "level": self.level.to_dict() if self.level else None,
            "target_count": self.target_count,
            "active": self.active,
            "response_count": response_count,
            "completion_percent": completion_percent,
        }


class SurveyResponse(TimestampMixin, db.Model):
    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(
        db.Integer,
        db.ForeignKey("survey_links.id", ondelete="CASCADE"),
        nullable=False,
    )
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    respondent_note = db.Column(db.String(240), nullable=False, default="")

    link = db.relationship("SurveyLink", back_populates="responses")
    answers = db.relationship(
        "SurveyAnswer",
        back_populates="response",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "link_id": self.link_id,
            "submitted_at": self.submitted_at.isoformat(),
            "answers": [answer.to_dict() for answer in self.answers],
        }


class SurveyAnswer(TimestampMixin, db.Model):
    __tablename__ = "survey_answers"
    __table_args__ = (
        db.UniqueConstraint("response_id", "item_id", name="uq_response_item"),
    )

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(
        db.Integer,
        db.ForeignKey("survey_responses.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id = db.Column(
        db.Integer,
        db.ForeignKey("form_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    option_id = db.Column(
        db.Integer,
        db.ForeignKey("form_options.id", ondelete="RESTRICT"),
        nullable=True,
    )
    option_label = db.Column(db.String(80), nullable=False, default="")
    score_weight = db.Column(db.Integer, nullable=False, default=0)
    text_value = db.Column(db.Text, nullable=False, default="")

    response = db.relationship("SurveyResponse", back_populates="answers")
    item = db.relationship("FormItem", back_populates="answers")
    option = db.relationship("FormOption", back_populates="answers")

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "option_id": self.option_id,
            "option_label": self.option_label,
            "score_weight": self.score_weight,
            "text_value": self.text_value,
        }
