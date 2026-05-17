import pandas as pd
import os
from collections import Counter
from typing import List, Dict, Any

# Adjust path based on execution location
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Ultimate_Career_Analytics_Expanded.csv")

class RecommendationEngine:
    def __init__(self):
        self.df = None
        self._load_data()

    def _load_data(self):
        try:
            # Check multiple possible locations for the dataset
            path_1 = os.path.join(os.path.dirname(__file__), "Ultimate_Career_Analytics_Expanded.csv")
            path_2 = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Ultimate_Career_Analytics_Expanded.csv")
            
            final_path = path_1 if os.path.exists(path_1) else path_2
            
            self.df = pd.read_csv(final_path)
            # Clean and normalize skills
            self.df['Skills'] = self.df['Skills'].fillna("").apply(lambda x: [s.strip().lower() for s in x.split(',')])
            # Career path grouping
            self.career_stats = self._build_career_stats()
        except Exception as e:
            print(f"Error loading dataset: {e}")

    def _build_career_stats(self) -> Dict[str, Any]:
        """Precomputes the most common skills and avg salary for each career path."""
        stats = {}
        if self.df is None:
            return stats
            
        for path in self.df['Career_Path'].unique():
            if pd.isna(path): continue
            
            path_df = self.df[self.df['Career_Path'] == path]
            
            # Aggregate skills
            all_skills = []
            for skills in path_df['Skills']:
                all_skills.extend(skills)
            
            # Get top skills
            skill_counts = Counter(all_skills)
            top_skills = [skill for skill, count in skill_counts.most_common(10) if skill]
            
            # Average salary
            avg_salary = path_df['Salary_INR'].mean()
            
            stats[path] = {
                "top_skills": top_skills,
                "avg_salary_inr": avg_salary,
                "demand_score": len(path_df) # Simple count as proxy for demand
            }
        return stats

    def calculate_match_score(self, user_skills: List[str], target_skills: List[str]) -> float:
        """Calculates Jaccard similarity between user skills and target skills."""
        if not target_skills or not user_skills:
            return 0.0
        
        user_set = set([s.lower() for s in user_skills])
        target_set = set(target_skills)
        
        intersection = user_set.intersection(target_set)
        
        # We emphasize how much of the target skills the user has (Recall-like metric)
        # rather than strict Jaccard, so partial matching looks better
        score = len(intersection) / len(target_set)
        return min(score * 100, 100.0)

    def get_career_matches(self, user_skills: List[str], user_interests: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Finds top matching career paths based on skills and dynamically generates a personalized mentor rationale."""
        if not self.career_stats or not user_skills:
            return []
            
        matches = []
        user_interests = user_interests or []
        for path, stats in self.career_stats.items():
            top_skills = stats["top_skills"]
            score = self.calculate_match_score(user_skills, top_skills)
            
            # Boost score slightly if user interests match the path generally
            interest_boost = 0.0
            for interest in user_interests:
                if interest.lower() in path.lower() or path.lower() in interest.lower():
                    interest_boost = 15.0 # 15% boost for direct interest match
            
            final_score = min(score + interest_boost, 100.0)
            
            if final_score > 0:
                user_set = set([s.lower() for s in user_skills])
                missing_skills = list(set(top_skills) - user_set)
                
                # Generate AI Mentor Rationale based on overlap
                matched_skills = list(user_set.intersection(set(top_skills)))
                if len(matched_skills) > 2:
                    rationale = f"Because of your strong foundation in {', '.join(matched_skills[:2].title())} and {matched_skills[-1].title()}, and your interest in {user_interests[0] if user_interests else 'tech'}, {path} is a highly viable path. You already possess {round(score)}% of the core competencies."
                elif len(matched_skills) > 0:
                    rationale = f"Your background in {matched_skills[0].title()} provides a stepping stone into {path}. With your interest in {user_interests[0] if user_interests else 'this field'}, focusing on closing the skill gap will make you highly competitive."
                else:
                    rationale = f"While you lack the immediate technical skills for {path}, your interest in {user_interests[0] if user_interests else 'growth'} makes this a great long-term target if you begin upskilling."

                # Generate categorized skills (mocked logic for categories since dataset is flat)
                core_skills = top_skills[:4]
                tools_skills = [s for s in top_skills[4:7] if 'tool' in s.lower() or 'bi' in s.lower() or 'tableau' in s.lower() or 'excel' in s.lower()]
                if not tools_skills: tools_skills = top_skills[4:6]
                data_handling = top_skills[6:]
                
                # Ordered Learning Path
                learning_path = []
                for i, ms in enumerate(missing_skills[:4]):
                    learning_path.append(f"Master {ms.title()}")
                learning_path.append("Work on 2 real-world portfolio projects")
                learning_path.append("Optimize Resume and Apply")

                matches.append({
                    "career_path": path,
                    "match_percentage": round(final_score, 1),
                    "required_skills": top_skills,
                    "missing_skills": missing_skills,
                    "categorized_skills": {
                        "Core Skills": core_skills,
                        "Tools & Technologies": tools_skills,
                        "Domain Specifics": data_handling
                    },
                    "learning_path": learning_path,
                    "avg_salary_inr": round(stats["avg_salary_inr"]),
                    "demand_score": stats["demand_score"],
                    "rationale": rationale
                })
                
        # Sort by match percentage descending
        matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        return matches[:limit]

    def get_internships(self, user_skills: List[str], education: str = "Undergraduate", limit: int = 5) -> List[Dict[str, Any]]:
        """Simulates finding internships from the dataset based on skills."""
        if self.df is None or not user_skills:
            return []
            
        user_set = set([s.lower() for s in user_skills])
        
        # Find rows with high overlap
        def internship_score(row_skills):
            target_set = set(row_skills)
            if not target_set: return 0
            return len(user_set.intersection(target_set)) / len(target_set)
            
        # Create copy to avoid SettingWithCopyWarning
        temp_df = self.df.copy()
        temp_df['match_score'] = temp_df['Skills'].apply(internship_score)
        
        # Sort and take top matches
        top_internships = temp_df.sort_values(by='match_score', ascending=False).head(limit)
        
        results = []
        # Group by role to avoid exact duplicates
        seen_roles = set()
        
        for _, row in top_internships.iterrows():
            role = row['Internship_Field']
            if pd.isna(role) or role in seen_roles:
                continue
                
            seen_roles.add(role)
            results.append({
                "role": role,
                "match_percentage": round(row['match_score'] * 100, 1),
                "required_skills": row['Skills'][:5]
            })
            
        return results

# Initialize a global instance
ai_engine = RecommendationEngine()
