from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models
from engine import ai_engine
from typing import List, Optional
from pydantic import BaseModel
import json

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str
    otp: str

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ASCENDRA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to ASCENDRA API"}

@app.get("/api/skills")
def get_all_skills():
    """Returns a list of top unique skills from the dataset for the frontend selector."""
    if ai_engine.df is None:
        raise HTTPException(status_code=500, detail="Engine not loaded")
        
    # Gather all skills
    all_skills = []
    for skills_list in ai_engine.df['Skills']:
        all_skills.extend(skills_list)
        
    from collections import Counter
    # Get top 300 skills to provide a rich searchable database
    top_skills = [skill.title() for skill, _ in Counter(all_skills).most_common(300) if skill]
    
    return {"skills": sorted(list(set(top_skills)))}

@app.get("/api/suggest-skills")
def suggest_skills(skills: str = ""):
    """Intelligently suggests related skills based on dataset co-occurrence."""
    current_skills = [s.strip().lower() for s in skills.split(',')] if skills else []
    
    if ai_engine.df is None:
        return {"suggestions": []}
        
    # Find rows that contain at least one of the current skills
    # Then count what OTHER skills are popular in those rows
    co_occurring = []
    
    if current_skills:
        for skills_list in ai_engine.df['Skills']:
            lower_skills = [s.lower() for s in skills_list]
            if any(s in lower_skills for s in current_skills):
                co_occurring.extend([s for s in skills_list if s.lower() not in current_skills])
    else:
        # If no skills, just return top overall
        for skills_list in ai_engine.df['Skills']:
            co_occurring.extend(skills_list)
            
    from collections import Counter
    suggestions = [skill.title() for skill, _ in Counter(co_occurring).most_common(5) if skill]
    
    return {"suggestions": list(set(suggestions))[:5]}

class AnalyzeRequest(BaseModel):
    full_name: Optional[str] = None
    education: str
    location: Optional[str] = None
    bio: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    interests: List[str]
    skills: List[str]
    profile_picture: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    method: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

# --- AUTH ENDPOINTS ---
@app.post("/api/auth/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == request.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = models.User(email=request.email, hashed_password=request.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    new_profile = models.Profile(user_id=new_user.id, full_name=request.name)
    db.add(new_profile)
    db.commit()
    
    return {"token": str(new_user.id), "user": {"name": request.name, "email": request.email}}

@app.post("/api/auth/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == request.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if request.otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    db_user.hashed_password = request.new_password
    db.commit()
    return {"message": "Password updated successfully"}

@app.post("/api/auth/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == request.email).first()
    if not db_user or db_user.hashed_password != request.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    profile = db.query(models.Profile).filter(models.Profile.user_id == db_user.id).first()
    return {"token": str(db_user.id), "user": {"name": profile.full_name if profile else "User", "email": db_user.email}}

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = int(authorization.split(" ")[1])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.get("/api/profile")
def get_profile(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    return {
        "name": profile.full_name,
        "education": profile.education_level or "",
        "bio": profile.bio or "",
        "location": profile.location or "",
        "linkedin": profile.linkedin_url or "",
        "github": profile.github_url or "",
        "streak_days": profile.streak_days,
        "analysis_data": json.loads(profile.resume_path) if profile.resume_path else None,
        "profile_picture": json.loads(profile.resume_path).get("profile_picture") if profile.resume_path else None
    }

@app.post("/api/profile")
def update_profile(request: AnalyzeRequest, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == user.id).first()
    if not profile:
        profile = models.Profile(user_id=user.id, full_name="User")
        db.add(profile)
    
    profile.education_level = request.education
    profile.bio = request.bio if request.bio else ", ".join(request.interests)
    
    if request.full_name: profile.full_name = request.full_name
    if request.location: profile.location = request.location
    if request.linkedin: profile.linkedin_url = request.linkedin
    if request.github: profile.github_url = request.github
    
    # Run analysis
    careers = ai_engine.get_career_matches(request.skills, request.interests, limit=3)
    internships = ai_engine.get_internships(request.skills, request.education, limit=4)
    
    roadmap = []
    recommended_action = None
    rationale = None
    
    if careers:
        top_career = careers[0]
        missing = top_career["missing_skills"]
        rationale = top_career["rationale"]
        
        if missing:
            recommended_action = f"Complete a course on {missing[0].title()} to boost your {top_career['career_path']} match."
            roadmap = [{"step": f"Learn {skill.title()}", "status": "pending"} for skill in missing[:3]]
            if roadmap: roadmap[0]["status"] = "active"
        else:
            recommended_action = f"Apply for {top_career['career_path']} roles! Your {request.education} background perfectly complements your skills."
            roadmap = [
                {"step": "Build Portfolio Project", "status": "active"},
                {"step": "Update Resume", "status": "pending"},
                {"step": "Apply for roles", "status": "pending"}
            ]

    analysis_data = {
        "skills": request.skills,
        "interests": request.interests,
        "career_matches": careers,
        "internships": internships,
        "recommended_action": recommended_action,
        "roadmap": roadmap,
        "top_rationale": rationale if careers else "We couldn't generate a specific rationale.",
        "profile_picture": request.profile_picture if request.profile_picture is not None else (json.loads(profile.resume_path).get("profile_picture") if profile.resume_path else None)
    }
    
    profile.resume_path = json.dumps(analysis_data)
    db.commit()
    
    return {"status": "success", "data": analysis_data}
@app.post("/api/analyze")
def analyze_profile_old(request: AnalyzeRequest):
    # Keep old endpoint for backwards compatibility if needed
    careers = ai_engine.get_career_matches(request.skills, request.interests, limit=3)
    internships = ai_engine.get_internships(request.skills, request.education, limit=4)
    return {"status": "success", "data": {"career_matches": careers, "internships": internships}}

import os
try:
    import google.generativeai as genai
except ImportError:
    genai = None

@app.post("/api/chat")
def chat_with_milliena(request: ChatRequest, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == user.id).first()
    
    if not profile:
        return {"response": "Hi! I'm Milliena ✨ I noticed you haven't set up your profile yet. Head over to the Profile tab to add your skills so I can provide personalized career guidance!"}
        
    analysis = json.loads(profile.resume_path) if profile.resume_path else {}
    skills = analysis.get("skills", [])
    matches = analysis.get("career_matches", [])
    roadmap = analysis.get("roadmap", [])
    
    msg = request.message
    
    # ---------------------------------------------------------
    # REAL LLM INTEGRATION (Google Gemini)
    # ---------------------------------------------------------
    api_key = "AIzaSyAPMcpSevFbLdhmZzrbdlOKJT8-HIn-1YY"
    
    if not api_key:
        return {"response": "API Key is missing."}

    # Configure Gemini
    if genai:
        genai.configure(api_key=api_key)
    
    # Construct Context Prompt
    system_prompt = f"""
You are Milliena, a highly intelligent, warm, and professional AI career mentor and global companion for the ASCENDRA platform.
You are NOT a robotic scripted chatbot. You are a conversational AI similar to ChatGPT, but with a specific personality: intelligent, supportive, visually expressive (use occasional emojis like ✨ or 🚀), and deeply knowledgeable about all topics (careers, tech, life advice, coding, startup, etc.).

User Profile Context:
- Full Name: {profile.full_name}
- Education Level: {profile.education_level}
- Current Skills: {', '.join(skills) if skills else 'None added yet'}
- Top Career Match: {matches[0]['career_path'] if matches else 'Unknown'}
- Active Roadmap Steps: {', '.join([r['step'] for r in roadmap]) if roadmap else 'None'}

Instructions:
1. Be highly conversational, fluid, and human-like.
2. Adapt to the user's topic—if they want to talk about space, talk about space. If they want coding help, write code blocks. If they ask for career advice, use the profile context provided above.
3. Keep responses reasonably concise but detailed enough to be valuable. Use markdown formatting.
4. Do NOT repeat the same phrases. Be dynamic.
5. If the user asks for suggestions, suggest concrete steps.
6. Do not mention that you are an AI language model by Google unless asked. You are Milliena, the AI soul of Ascendra.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
        
        # Build chat history for the model
        formatted_history = []
        for m in request.history:
            role = "user" if m.role == "user" else "model"
            formatted_history.append({"role": role, "parts": [m.text]})
            
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(msg)
        
        # Try to extract suggestion cards if we want, but for now we rely on the LLM text.
        # We can dynamically suggest standard cards to keep UI engaging.
        cards = ["Analyze My Skills", "Build My Roadmap", "Suggest Projects"] if not skills else ["Review Roadmap", "Find Internships", "Interview Prep"]
        
        return {"response": response.text, "suggestion_cards": cards}
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"response": "I encountered a slight hiccup connecting to my neural network. Could you try asking that again?"}

