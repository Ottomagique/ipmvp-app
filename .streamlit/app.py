import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
from datetime import datetime

# Importer l'API météo et le modèle optimisé
from weather_api import WeatherAPI
from optimized_model import OptimizedModelIPMVP

# Configuration de la page
st.set_page_config(
    page_title="Analyse IPMVP avec Météo",
    page_icon="📊",
    layout="wide"
)

# Fonction d'authentification
def check_password():
    """Retourne True si l'utilisateur a entré le bon mot de passe"""
    if "authentication_status" in st.session_state:
        return st.session_state["authentication_status"]
        
    st.title("Connexion à l'application IPMVP")
    
    # Cet espace fait de la place pour la zone de login
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Centrer le formulaire de login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Veuillez vous connecter")
        username = st.text_input("Nom d'utilisateur", key="username")
        password = st.text_input("Mot de passe", type="password", key="password")
        
        if st.button("Connexion"):
            # Vérifier si secrets est disponible (déploiement)
            try:
                if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
                    st.session_state["authentication_status"] = True
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect")
            except:
                # Mode développement - accepter des identifiants par défaut
                if username == "admin" and password == "admin":
                    st.warning("Mode développement: utilisation des identifiants par défaut")
                    st.session_state["authentication_status"] = True
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect")
    
    return False

# Vérifier l'authentification avant d'afficher l'application
if not check_password():
    st.stop()  # Arrête l'exécution de l'application si non authentifié

# Fonction pour charger les données
@st.cache_data
def load_data(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier: {e}")
        return None

# Titre de l'application
st.title("📊 Analyse IPMVP avec Données Météo")
st.markdown("""
Cette application vous permet d'analyser vos données de consommation énergétique en les corrélant 
avec des données météorologiques récupérées automatiquement. L'application utilise les modèles conformes
au protocole IPMVP (International Performance Measurement and Verification Protocol).
""")

# Barre latérale pour les paramètres
st.sidebar.header("Configuration")

# Section 1: Chargement des données
st.sidebar.subheader("1. Données de consommation")
uploaded_file = st.sidebar.file_uploader("Chargez votre fichier Excel de consommation", type=["xlsx", "xls"])

# Afficher un dataset d'exemple si aucun fichier n'est chargé
if uploaded_file is None:
    st.info("👆 Veuillez charger votre fichier Excel contenant les données de consommation.")
    
    # Créer un exemple de données
    example_data = {
        'Date': pd.date_range(start='2023-01-01', periods=12, freq='ME'),
        'Consommation': [570, 467, 490, 424, 394, 350, 320, 310, 370, 420, 480, 540]
    }
    example_df = pd.DataFrame(example_data)
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("Exemple de données attendues:")
        st.dataframe(example_df)
    
    with col2:
        st.write("Structure recommandée:")
        st.markdown("""
        - Une colonne avec les dates
        - Une colonne avec les consommations
        - Jusqu'à 4 colonnes pour des variables explicatives (ex: DJU)
        """)
    
    proceed = False
else:
    # Charger les données
    df = load_data(uploaded_file)
    
    if df is not None:
        st.subheader("Données chargées")
        st.dataframe(df)
        
        # Identification automatique des colonnes
        date_col = None
        conso_col = None
        
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or 'date' in str(col).lower():
                date_col = col
            elif 'conso' in str(col).lower() or 'energy' in str(col).lower() or 'energie' in str(col).lower():
                conso_col = col
        
        # Sélection des colonnes
        st.sidebar.write("Colonnes identifiées:")
        date_col = st.sidebar.selectbox("Colonne de date", options=df.columns, index=0 if date_col is None else list(df.columns).index(date_col))
        conso_col = st.sidebar.selectbox("Colonne de consommation", options=df.columns, index=1 if conso_col is None else list(df.columns).index(conso_col))
        
        # Sélection des variables explicatives
        st.sidebar.write("Variables explicatives:")
        var_options = [col for col in df.columns if col != date_col and col != conso_col]
        
        # Utilisation de multiselect pour permettre à l'utilisateur de choisir plusieurs variables
        selected_vars = st.sidebar.multiselect(
            "Sélectionnez jusqu'à 4 variables", 
            options=var_options,
            default=[col for col in var_options if 'dju' in str(col).lower() or 'degre' in str(col).lower()][:4]
        )
        
        # S'assurer que la colonne de date est au format datetime
        try:
            df[date_col] = pd.to_datetime(df[date_col])
        except:
            st.warning(f"La colonne {date_col} n'a pas pu être convertie en date.")
        
        proceed = True
    else:
        proceed = False

# Section 2: Données météo et configuration du modèle
if proceed:
    # Section 2: Données météo
    st.sidebar.subheader("2. Données météo")
    use_weather_api = st.sidebar.checkbox("Récupérer données météo automatiquement", value=True)

    if use_weather_api:
        # Types de saisie pour la localisation
        location_type = st.sidebar.radio(
            "Type de localisation", 
            options=["Ville", "Coordonnées GPS"], 
            index=0
        )
        
        if location_type == "Ville":
            city = st.sidebar.text_input("Ville", "Paris")
            location = f"{city},FR"
        else:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                lat = st.number_input("Latitude", value=48.8566, format="%.4f")
            with col2:
                lon = st.number_input("Longitude", value=2.3522, format="%.4f")
            location = f"{lat},{lon}"
        
        # Bases de température
        st.sidebar.subheader("Bases de température")
        include_dju = st.sidebar.checkbox("Inclure DJU (chauffage)", value=True)
        if include_dju:
            dju_bases = st.sidebar.multiselect(
                "Bases DJU (°C)", 
                options=[15, 16, 17, 18, 19, 20],
                default=[18]
            )
        else:
            dju_bases = []
            
        include_djf = st.sidebar.checkbox("Inclure DJF (climatisation)", value=True)
        if include_djf:
            djf_bases = st.sidebar.multiselect(
                "Bases DJF (°C)", 
                options=[20, 21, 22, 23, 24, 25, 26],
                default=[22]
            )
        else:
            djf_bases = []

    # Section 3: Configuration du modèle
    st.sidebar.subheader("3. Configuration du modèle")
    
    # Nombre maximum de variables
    max_features = st.sidebar.slider("Nombre maximum de variables", 1, 4, min(4, len(selected_vars) if selected_vars else 1))
    
    # Bouton pour lancer l'analyse
    if st.sidebar.button("🚀 Lancer l'analyse IPMVP"):
        if not selected_vars and not use_weather_api:
            st.warning("Vous n'avez sélectionné aucune variable explicative et désactivé l'API météo. L'analyse risque de ne pas être pertinente.")
        
        st.subheader("Analyse IPMVP en cours...")
        
        # Dates min et max à partir des données
        start_date = df[date_col].min().strftime('%Y-%m-%d')
        end_date = df[date_col].max().strftime('%Y-%m-%d')
        
        st.write(f"Période analysée: du {start_date} au {end_date}")
        
        # Afficher la progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Variables pour l'analyse
        analysis_vars = list(selected_vars)
        dates_for_analysis = df[date_col]
        consumption_data = df.copy()
        
        # Si l'API météo est activée, récupérer et fusionner les données
        if use_weather_api:
            status_text.text("Récupération des données météo...")
            progress_bar.progress(10)
            
            # Initialiser l'API météo
            weather_api = WeatherAPI()
            
            # Récupérer les données
            weather_data = weather_api.get_weather_data(
                location,
                start_date,
                end_date,
                bases_dju=dju_bases,
                bases_djf=djf_bases
            )
            
            if not weather_data.empty:
                st.subheader("Données météo mensuelles")
                st.dataframe(weather_data)
                
                # Fusionner avec les données de consommation
                status_text.text("Fusion des données...")
                progress_bar.progress(30)
                
                # Convertir les dates en période mensuelle
                consumption_data['month'] = pd.to_datetime(consumption_data[date_col]).dt.to_period('M')
                
                # Fusion
                merged_df = pd.merge(consumption_data, weather_data, on='month', how='inner')
                
                # Vérifier la fusion
                if len(merged_df) < len(consumption_data):
                    st.warning(f"{len(consumption_data) - len(merged_df)} lignes n'ont pas pu être fusionnées")
                
                st.subheader("Données fusionnées")
                st.dataframe(merged_df)
                
                # Variables météo disponibles
                meteo_vars = [col for col in weather_data.columns 
                             if col not in ['date', 'month', 'localisation'] 
                             and any(x in col for x in ['dju', 'djf', 'temp', 'sun'])]
                
                # Ajouter les variables météo à la liste des variables d'analyse
                all_available_vars = analysis_vars + [v for v in meteo_vars if v not in analysis_vars]
                
                # Laisser l'utilisateur choisir les variables à utiliser
                selected_analysis_vars = st.multiselect(
                    "Variables à utiliser pour l'analyse IPMVP",
                    options=all_available_vars,
                    default=[v for v in all_available_vars if "dju_base_18" in v] if "dju_base_18" in all_available_vars else all_available_vars[:1]
                )
                
                if selected_analysis_vars:
                    # Mettre à jour les variables d'analyse
                    analysis_vars = selected_analysis_vars
                    consumption_data = merged_df
                    dates_for_analysis = merged_df['date_x'] if 'date_x' in merged_df.columns else merged_df[date_col]
                else:
                    st.warning("Aucune variable sélectionnée pour l'analyse. Utilisation des variables initiales.")
        
        # Continuer avec l'analyse IPMVP
        status_text.text("Préparation des données pour l'analyse IPMVP...")
        progress_bar.progress(50)
        
        # Préparation des données
        X = consumption_data[analysis_vars]
        y = consumption_data[conso_col]
        
        # Création et entrainement du modèle IPMVP
        status_text.text("Recherche du meilleur modèle... Priorité aux modèles simples")
        
        modele_ipmvp = OptimizedModelIPMVP()
        success = modele_ipmvp.trouver_meilleur_modele(
            X, y, max_features=max_features,
            progress_callback=lambda p: progress_bar.progress(50 + p * 0.4)
        )
        
        if success:
            status_text.text("Analyse terminée avec succès!")
            
            # Rapport
            rapport = modele_ipmvp.generer_rapport(y_original=y)
            st.subheader("Résultats de l'analyse IPMVP")
            st.text(rapport)
            
            # Visualisation
            st.subheader("Visualisation des résultats")
            results_df = modele_ipmvp.visualiser_resultats(X, y, dates=dates_for_analysis)
            
            # Afficher les graphiques
            st.image('resultats_modele_ipmvp.png')
            st.image('comparaison_consommations.png')
            
            # Téléchargement des résultats
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Données d\'origine', index=False)
                if 'merged_df' in locals():
                    merged_df.to_excel(writer, sheet_name='Données avec météo', index=False)
                if "Info" not in results_df.columns:  # Si des résultats valides
                    results_df.to_excel(writer, sheet_name='Résultats', index=False)
                else:
                    pd.DataFrame({"Message": ["Pas de résultats valides"]}).to_excel(writer, sheet_name='Résultats', index=False)
                    
            st.download_button(
                label="📥 Télécharger les résultats",
                data=buffer.getvalue(),
                file_name="resultats_ipmvp.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            status_text.text("Analyse terminée, mais aucun modèle conforme trouvé.")
            st.warning("Aucun modèle conforme aux critères IPMVP n'a pu être trouvé avec ces données. Essayez d'ajouter plus de variables explicatives ou d'assouplir les critères.")

        # Terminer la barre de progression
        progress_bar.progress(100)

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Développé avec ❤️ pour l'analyse IPMVP")
