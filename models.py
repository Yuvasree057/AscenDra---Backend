from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    is_premium = Column(Boolean, default=False)
    
    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String)
    education_level = Column(String)
    location = Column(String)
    bio = Column(Text)
    github_url = Column(String)
    linkedin_url = Column(String)
    resume_path = Column(String)
    streak_days = Column(Integer, default=0)
    
    user = relationship("User", back_populates="profile")

class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String)

class UserSkill(Base):
    __tablename__ = "user_skills"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"))
    proficiency = Column(Float, default=1.0)

class CareerMatch(Base):
    __tablename__ = "career_matches"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role_title = Column(String)
    match_percentage = Column(Float)
    rationale = Column(Text)

class Internship(Base):
    __tablename__ = "internships"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String)
    role = Column(String)
    stipend = Column(String)
    is_remote = Column(Boolean)
    required_skills = Column(String)

class RoadmapProgress(Base):
    __tablename__ = "roadmap_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    step_title = Column(String)
    is_completed = Column(Boolean, default=False)
