import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.metrics import r2_score, mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# Cache pour éviter de recalculer les modèles déjà évalués
@st.cache_data
def evaluer_combinaison(X, y, features, _type="linear"):
    """Évalue une combinaison de variables et retourne les métriques (mis en cache)"""
    X_subset = X[features]
    
    if _type == "poly":
        poly = PolynomialFeatures(degree=2, include_bias=False)
        X_subset = poly.fit_transform(X_subset)
        model = LinearRegression()
    else:
        model = LinearRegression()
    
    model.fit(X_subset, y)
    y_pred = model.predict(X_subset)
    
    r2 = r2_score(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    cv = rmse / np.mean(y) if np.mean(y) != 0 else np.inf
    bias = np.mean(y_pred - y) / np.mean(y) if np.mean(y) != 0 else np.inf
    
    conforme = r2 > 0.75 and abs(cv) < 0.2 and abs(bias) < 0.01
    
    return {
        'r2': r2,
        'cv': cv,
        'bias': bias,
        'model': model,
        'conforme': conforme,
        'y_pred': y_pred
    }

class OptimizedModelIPMVP:
    def __init__(self):
        self.best_model = None
        self.best_features = None
        self.best_formula = None
        self.best_r2 = 0
        self.best_cv = None
        self.best_bias = None
        self.best_model_type = None
        self.best_coefficients = None
        self.best_intercept = None
        self.best_y_pred = None
    
    def trouver_meilleur_modele(self, X, y, max_features=4, progress_callback=None):
        """Version optimisée qui utilise le cache et prioritise les modèles prometteurs"""
        # Recherche rapide: commencer par vérifier la colonne DJU seule
        dju_colonne = None
        for col in X.columns:
            if 'dju' in str(col).lower():
                dju_colonne = col
                break
        
        if dju_colonne:
            # Tester le modèle DJU d'abord (le plus susceptible d'être conforme)
            result = evaluer_combinaison(X, y, [dju_colonne])
            if result['conforme']:
                self._update_best_model(result, [dju_colonne], "Linéaire (E = a×DJU + c)", X, y)
                # Si on trouve un modèle DJU conforme, terminer rapidement
                return True
        
        # Si le modèle DJU n'est pas conforme, tester d'autres combinaisons
        from itertools import combinations
        
        # Limiter le nombre de variables à tester
        max_features = min(max_features, len(X.columns))
        models_tested = 0
        total_models = sum(len(list(combinations(X.columns, i))) for i in range(1, max_features + 1))
        
        # Tester les combinaisons de variables une par une
        for n_features in range(1, max_features + 1):
            feature_combos = list(combinations(X.columns, n_features))
            for i, feature_subset in enumerate(feature_combos):
                feature_subset = list(feature_subset)
                
                # Mettre à jour la progression
                models_tested += 1
                if progress_callback:
                    progress_callback(models_tested / total_models)
                
                # Évaluer le modèle linéaire
                result = evaluer_combinaison(X, y, feature_subset)
                if result['conforme'] and result['r2'] > self.best_r2:
                    self._update_best_model(result, feature_subset, "Linéaire", X, y)
                
                # Évaluer le modèle polynomial (uniquement pour 1-2 variables)
                if n_features <= 2:
                    result = evaluer_combinaison(X, y, feature_subset, _type="poly")
                    if result['conforme'] and result['r2'] > self.best_r2:
                        self._update_best_model(result, feature_subset, "Polynomiale (degré 2)", X, y)
        
        return self.best_model is not None
    
    def _update_best_model(self, result, features, model_type, X, y):
        """Met à jour le meilleur modèle avec les résultats"""
        self.best_r2 = result['r2']
        self.best_cv = result['cv']
        self.best_bias = result['bias']
        self.best_model = result['model']
        self.best_model_type = model_type
        self.best_features = features
        self.best_y_pred = result['y_pred']
        
        if hasattr(self.best_model, 'coef_'):
            self.best_coefficients = self.best_model.coef_
            self.best_intercept = self.best_model.intercept_
        
        self._construire_formule()
    
    def _construire_formule(self):
        """Construit la formule du meilleur modèle"""
        if self.best_model is None:
            self.best_formula = "Aucun modèle valide trouvé"
            return
        
        formula = f"{self.best_intercept:.4f}"
        for i, coef in enumerate(self.best_coefficients):
            feature_name = self.best_features[i]
            formula += f" + {coef:.4f} × ({feature_name})"
            
        self.best_formula = formula
    
    def generer_rapport(self, y_original=None):
        """Génère un rapport sur le meilleur modèle"""
        if self.best_model is None:
            return "❌ Aucun modèle valide n'a pu être entraîné."
        
        # S'assurer qu'on peut calculer le RMSE
        if y_original is None or self.best_y_pred is None:
            rmse = "N/A"
        else:
            rmse = np.sqrt(mean_squared_error(y_original, self.best_y_pred))
        
        rapport = f"""
        ✅ RAPPORT IPMVP - {self.best_model_type}
        ------------------------------------------------------------
        📊 Variables sélectionnées : {self.best_features}
        📊 Équation du modèle : {self.best_formula}
        📈 R² : {self.best_r2:.4f} (seuil IPMVP > 0.75)
        📉 RMSE : {rmse if isinstance(rmse, str) else f"{rmse:.4f}"}
        📊 CV(RMSE) : {self.best_cv:.4f} (seuil IPMVP < 0.2)
        📊 NMBE (Biais) : {self.best_bias:.8f} (seuil IPMVP < 0.01)
        
        ✅ Modèle conforme aux critères IPMVP 🎯
        """
        return rapport
    
    def visualiser_resultats(self, X, y, dates=None):
        """Crée des visualisations pour le meilleur modèle"""
        if self.best_model is None:
            return pd.DataFrame({"Info": ["Aucun modèle valide trouvé"]})
        
        # Calculer les prédictions
        X_subset = X[self.best_features]
        if "Polynomiale" in self.best_model_type:
            poly = PolynomialFeatures(degree=2, include_bias=False)
            X_subset = poly.fit_transform(X_subset)
        
        y_pred = self.best_model.predict(X_subset)
        
        # Créer un DataFrame pour l'analyse
        results_df = pd.DataFrame({
            'Valeur_Réelle': y,
            'Valeur_Prédite': y_pred,
            'Erreur': y - y_pred
        })
        
        # Ajouter les dates si disponibles
        if dates is not None:
            results_df['Date'] = dates
        
        # Créer les visualisations
        self._creer_graphiques(results_df, dates)
        
        return results_df
    
    def _creer_graphiques(self, results_df, dates=None):
        """Crée et sauvegarde les graphiques"""
        # Graphique 1: Comparaison des métriques
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Valeurs réelles vs prédites
        axes[0, 0].scatter(results_df['Valeur_Réelle'], results_df['Valeur_Prédite'], alpha=0.6)
        axes[0, 0].plot([results_df['Valeur_Réelle'].min(), results_df['Valeur_Réelle'].max()], 
                     [results_df['Valeur_Réelle'].min(), results_df['Valeur_Réelle'].max()], 'r--')
        axes[0, 0].set_title('Valeurs Réelles vs Prédites')
        axes[0, 0].set_xlabel('Valeurs Réelles')
        axes[0, 0].set_ylabel('Valeurs Prédites')
        axes[0, 0].grid(True)
        
        # Distribution des erreurs
        sns.histplot(results_df['Erreur'], kde=True, ax=axes[0, 1])
        axes[0, 1].set_title('Distribution des Erreurs')
        axes[0, 1].set_xlabel('Erreur')
        axes[0, 1].grid(True)
        
        # Erreurs vs valeurs prédites
        axes[1, 0].scatter(results_df['Valeur_Prédite'], results_df['Erreur'], alpha=0.6)
        axes[1, 0].axhline(y=0, color='r', linestyle='--')
        axes[1, 0].set_title('Erreurs vs Valeurs Prédites')
        axes[1, 0].set_xlabel('Valeurs Prédites')
        axes[1, 0].set_ylabel('Erreur')
        axes[1, 0].grid(True)
        
        # Importance des variables
        if len(self.best_features) > 0:
            coefs = pd.DataFrame({
                'Variable': self.best_features,
                'Coefficient': np.abs(self.best_coefficients)
            })
            coefs = coefs.sort_values('Coefficient', ascending=False)
            sns.barplot(x='Coefficient', y='Variable', data=coefs, ax=axes[1, 1])
            axes[1, 1].set_title('Importance des Variables')
            axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.savefig('resultats_modele_ipmvp.png')
        
        # Graphique 2: Consommation mesurée vs calculée
        plt.figure(figsize=(15, 6))
        
        if dates is not None and 'Date' in results_df.columns:
            # Trier par date
            results_df = results_df.sort_values('Date')
            
            # Barres pour les valeurs réelles
            plt.bar(range(len(results_df)), results_df['Valeur_Réelle'], color='royalblue', 
                   width=0.6, label='Conso mesurée')
            
            # Ligne pour les valeurs prédites
            plt.plot(range(len(results_df)), results_df['Valeur_Prédite'], color='orangered',
                    marker='o', linestyle='-', linewidth=2, markersize=8, label='Conso calculée')
            
            # Formater l'axe des x avec les dates
            date_labels = [d.strftime('%b-%y') if hasattr(d, 'strftime') else d for d in results_df['Date']]
            plt.xticks(range(len(results_df)), date_labels, rotation=45)
        else:
            plt.bar(range(len(results_df)), results_df['Valeur_Réelle'], color='royalblue', 
                   width=0.6, label='Conso mesurée')
            plt.plot(range(len(results_df)), results_df['Valeur_Prédite'], color='orangered',
                    marker='o', linestyle='-', linewidth=2, markersize=8, label='Conso calculée')
        
        plt.title('Comparaison Consommation Mesurée vs Calculée')
        plt.ylabel('Consommation')
        plt.legend()
        plt.grid(True, axis='y')
        
        # Ajouter la formule d'ajustement
        plt.figtext(0.5, 0.01, f"Formule d'ajustement: {self.best_formula}", 
                   ha='center', fontsize=12, bbox={"facecolor":"white", "alpha":0.8, "pad":5})
        
        plt.tight_layout()
        plt.savefig('comparaison_consommations.png')