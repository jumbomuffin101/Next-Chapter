
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

def new_id():
    return uuid.uuid4()


# ============================================================
# ALUMNI
# ============================================================

class Alumni(Base):
    __tablename__ = "alumni"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    first_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    last_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String(30))
    city: Mapped[str | None] = mapped_column(String(100))
    cohort: Mapped[str | None] = mapped_column(String(100))
    graduation_year: Mapped[int | None] = mapped_column(Integer)

    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    work_experience = relationship(
        "WorkExperience",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )

    education = relationship(
        "Education",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )

    skills = relationship(
        "Skill",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )

    certifications = relationship(
        "Certification",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )

    resume_uploads = relationship(
        "ResumeUpload",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )

    salary_records = relationship(
        "SalaryRecord",
        back_populates="alumni",
        cascade="all, delete-orphan",
    )


# ============================================================
# WORK EXPERIENCE
# ============================================================

class WorkExperience(Base):
    __tablename__ = "work_experience"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    employer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(String(150))

    start_date: Mapped[date | None] = mapped_column(Date)

    end_date: Mapped[date | None] = mapped_column(Date)

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(
        String(30),
        default="resume",
        nullable=False,
    )

    alumni = relationship(
        "Alumni",
        back_populates="work_experience",
    )


# ============================================================
# EDUCATION
# ============================================================

class Education(Base):
    __tablename__ = "education"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    school: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    degree: Mapped[str | None] = mapped_column(String(150))

    field_of_study: Mapped[str | None] = mapped_column(
        String(150)
    )

    start_year: Mapped[int | None] = mapped_column(Integer)

    graduation_year: Mapped[int | None] = mapped_column(Integer)

    alumni = relationship(
        "Alumni",
        back_populates="education",
    )


# ============================================================
# SKILLS
# ============================================================

class Skill(Base):
    __tablename__ = "skills"

    __table_args__ = (
        UniqueConstraint(
            "alumni_id",
            "name",
            name="uq_alumni_skill",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    alumni = relationship(
        "Alumni",
        back_populates="skills",
    )


# ============================================================
# CERTIFICATIONS
# ============================================================

class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    issuer: Mapped[str | None] = mapped_column(String(255))

    alumni = relationship(
        "Alumni",
        back_populates="certifications",
    )


# ============================================================
# RESUME UPLOADS
# ============================================================

class ResumeUpload(Base):
    __tablename__ = "resume_uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    parsed_data: Mapped[dict | None] = mapped_column(JSON)

    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    alumni = relationship(
        "Alumni",
        back_populates="resume_uploads",
    )


# ============================================================
# SALARY RECORDS
# ============================================================

class SalaryRecord(Base):
    __tablename__ = "salary_records"

    __table_args__ = (
        CheckConstraint(
            "source IN ('self_reported', 'estimated')",
            name="valid_salary_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    alumni_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alumni.id"),
        nullable=False,
        index=True,
    )

    salary_min: Mapped[float | None] = mapped_column(
        Numeric(12, 2)
    )

    salary_max: Mapped[float | None] = mapped_column(
        Numeric(12, 2)
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    effective_date: Mapped[date | None] = mapped_column(Date)

    # The job this salary was for, picked in the dashboard's salary history. Deleting the job keeps the salary, unlinked.
    work_experience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_experience.id", ondelete="SET NULL"),
    )

    alumni = relationship(
        "Alumni",
        back_populates="salary_records",
    )


# ============================================================
# SALARY BENCHMARKS
# ============================================================

class SalaryBenchmark(Base):
    __tablename__ = "salary_benchmarks"

    __table_args__ = (
        UniqueConstraint(
            "title_family",
            "city",
            "experience_band",
            name="uq_salary_benchmark",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    title_family: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    experience_band: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    salary_min: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    salary_max: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )


# ============================================================
# GREENHOUSE JOB LISTINGS
# ============================================================

class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint(
            "board_token",
            "greenhouse_job_id",
            name="uq_greenhouse_job",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
    )

    board_token: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    greenhouse_job_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(String(255))

    absolute_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    salary_min: Mapped[float | None] = mapped_column(
        Numeric(12, 2)
    )

    salary_max: Mapped[float | None] = mapped_column(
        Numeric(12, 2)
    )

    is_remote: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class NewsletterSubscription(Base):
    """Separate, explicit consent; missing row means OFF. Never networking consent."""
    __tablename__ = "newsletter_subscriptions"
    alumni_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alumni.id", ondelete="CASCADE"), primary_key=True)
    subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    token_nonce: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NewsletterDelivery(Base):
    __tablename__ = "newsletter_deliveries"
    __table_args__ = (UniqueConstraint("alumni_id", "month", name="uq_newsletter_alumni_month"),
                     CheckConstraint("status IN ('dry_run','attempting','accepted','retryable','failed','unknown')", name="newsletter_delivery_status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    alumni_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alumni.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
