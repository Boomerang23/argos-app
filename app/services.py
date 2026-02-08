from sqlalchemy.orm import Session
from thefuzz import process, fuzz
from . import models

class ScreeningService:
    def check_name(self, db: Session, name: str, threshold: int = 80):
        """
        Vérifie un nom par rapport à la base de données PostgreSQL.
        """
        # 1. On récupère TOUS les noms de la table Sanctions
        sanctions_query = db.query(models.Sanction).all()
        
        # Si la liste est vide, on arrête tout de suite
        if not sanctions_query:
            return []
            
        # On extrait juste les noms pour l'algorithme
        db_names = [s.name for s in sanctions_query]
        
        # 2. On compare le nom d'entrée avec la liste de la DB
        matches = process.extract(name, db_names, scorer=fuzz.token_sort_ratio, limit=3)
        
        results = []
        for match_name, score in matches:
            if score >= threshold:
                results.append({
                    "matched_name": match_name,
                    "score": score,
                    "alert": True
                })
        
        return results