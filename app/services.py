from sqlalchemy.orm import Session
from thefuzz import process, fuzz
from . import models

class ScreeningService:
    def check_name(self, db: Session, name: str, threshold: int = 80):
        """
        Vérifie un nom par rapport à la base de données PostgreSQL avec thefuzz.
        Utilise token_set_ratio pour gérer les prénoms composés ou manquants.
        """
        # 1. On récupère TOUS les profils de la table Sanctions
        sanctions_query = db.query(models.Sanction).all()
        
        # Si la liste est vide, on arrête tout de suite
        if not sanctions_query:
            return []
            
        # On crée un dictionnaire pour se souvenir de la source de chaque nom
        sanctions_dict = {s.name: getattr(s, 'list_source', 'Liste de Surveillance') for s in sanctions_query}
        db_names = list(sanctions_dict.keys())
        
        # 2. On compare le nom d'entrée avec la liste de la DB
        # --- CORRECTION MAJEURE ICI (token_set_ratio au lieu de token_sort_ratio) ---
        matches = process.extract(name, db_names, scorer=fuzz.token_set_ratio, limit=3)
        
        results = []
        for match_name, score in matches:
            if score >= threshold:
                results.append({
                    "matched_name": match_name,
                    "score": round(score, 2),
                    "list_source": sanctions_dict[match_name], # On récupère la vraie source !
                    "alert": True
                })
        
        return results
