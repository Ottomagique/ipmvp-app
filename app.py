import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
from datetime import datetime
import requests

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

# Classe pour l'API météo
class WeatherAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or "ZE3U556AFCCFHBXSFC95XRABC"
        self.base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    
    @st.cache_data(ttl=3600)
    def get_weather_data(self, location, start_date, end_date, bases_dju=[16, 18, 19], bases_djf=[22, 24, 26]):
        """
        Récupère les données météo pour une période donnée
        
        Parameters:
        -----------
        location : str
            Ville française (ex: "Paris,FR", "Lyon,FR") ou coordonnées GPS
        start_date : str
            Date de début au format 'YYYY-MM-DD'
        end_date : str
            Date de fin au format 'YYYY-MM-DD'
        bases_dju : list
            Liste des températures de base pour les DJU (par défaut [16, 18, 19])
        bases_djf : list
            Liste des températures de base pour les DJF (par défaut [22, 24, 26])
            
        Returns:
        --------
        pd.DataFrame
            Données mensuelles avec DJU, DJF pour différentes bases
        """
        # S'assurer que la localisation se termine par ,FR pour les villes françaises
        if ',' not in location and not (location.replace('.', '').replace('-', '').isdigit()):
            location = f"{location},FR"
            
        url = f"{self.base_url}/{location}/{start_date}/{end_date}"
        
        params = {
            'unitGroup': 'metric',
            'include': 'days',
            'key': self.api_key,
            'contentType': 'json',
            'elements': 'datetime,tempmax,tempmin,temp,humidity,precip,sunhours,dew,windspeed,cloudcover'
        }
        
        try:
            with st.spinner(f"Récupération des données météo pour {location}..."):
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Extraire la localisation exacte utilisée
            resolved_address = data.get('resolvedAddress', location)
            st.success(f"Données météo récupérées pour: {resolved_address}")
            
            # Extraire les données quotidiennes
            daily_data = []
            for day in data.get('days', []):
                day_data = {
                    'date': day.get('datetime'),
                    'temp_max': day.get('tempmax'),
                    'temp_min': day.get('tempmin'),
                    'temp_mean': day.get('temp'),
                    'humidity': day.get('humidity'),
                    'precip': day.get('precip'),
                    'sunshine_hours': day.get('sunhours', 0),
                    'cloud_cover': day.get('cloudcover', 0)
                }
                
                # Calculer DJU pour différentes bases
                for base in bases_dju:
                    day_data[f'dju_base_{base}'] = max(0, base - day.get('temp'))
                
                # Calculer DJF pour différentes bases
                for base in bases_djf:
                    day_data[f'djf_base_{base}'] = max(0, day.get('temp') - base)
                
                daily_data.append(day_data)
            
            # Convertir en DataFrame
            weather_df = pd.DataFrame(daily_data)
            
            # Agréger les données par mois
            monthly_df = self._aggregate_monthly(weather_df)
            
            # Ajouter la localisation utilisée
            monthly_df['localisation'] = resolved_address
            
            return monthly_df
            
        except Exception as e:
            st.error(f"Erreur lors de la récupération des données météo: {str(e)}")
            return pd.DataFrame()
    
    def _aggregate_monthly(self, df):
        """Agrège les données quotidiennes en mensuelles"""
        if df.empty:
            return pd.DataFrame()
        
        # Convertir la date en datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Extraire le mois
        df['month'] = df['date'].dt.to_period('M')
        
        # Identifier les colonnes par type pour savoir comment les agréger
        dju_cols = [col for col in df.columns if 'dju_base' in col]
        djf_cols = [col for col in df.columns if 'djf_base' in col]
        
        # Créer le dictionnaire d'agrégation
        agg_dict = {}
        
        # DJU, DJF, précip, ensoleillement -> somme
        for col in dju_cols + djf_cols + ['precip', 'sunshine_hours']:
            if col in df.columns:
                agg_dict[col] = 'sum'
        
        # Températures moyennes, humidité -> moyenne
        for col in ['temp_mean', 'humidity', 'cloud_cover']:
            if col in df.columns:
                agg_dict[col] = 'mean'
        
        # Températures max/min
        if 'temp_max' in df.columns:
            agg_dict['temp_max'] = 'max'
        if 'temp_min' in df.columns:
            agg_dict['temp_min'] = 'min'
        
        # Agréger par mois
        monthly_df = df.groupby('month').agg(agg_dict).reset_index()
        
        # Convertir le mois en date (1er jour du mois)
        monthly_df['date'] = monthly_df['month'].dt.to_timestamp()
        
        return monthly_df

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
        'Date': pd.date_range(start='2023-01-01', periods=12, freq='MS'),
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
        # Dates min et max à partir des données
        start_date = df[date_col].min().strftime('%Y-%m-%d')
        end_date = df[date_col].max().strftime('%Y-%m-%d')
        
        st.subheader("Analyse IPMVP en cours...")
        
        st.write(f"Période analysée: du {start_date} au {end_date}")
        
        # Afficher la progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
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
                df['month'] = pd.to_datetime(df[date_col]).dt.to_period('M')
                
                # Fusion
                merged_df = pd.merge(df, weather_data, on='month', how='inner')
                
                # Vérifier la fusion
                if len(merged_df) < len(df):
                    st.warning(f"{len(df) - len(merged_df)} lignes n'ont pas pu être fusionnées")
                
                st.subheader("Données fusionnées")
                st.dataframe(merged_df)
                
                # Téléchargement des données météo
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    weather_data.to_excel(writer, sheet_name='Données Météo', index=False)
                    merged_df.to_excel(writer, sheet_name='Données Fusionnées', index=False)
                
                st.download_button(
                    label="📥 Télécharger les données météo et fusionnées",
                    data=buffer.getvalue(),
                    file_name="donnees_meteo_ipmvp.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Variables météo disponibles pour l'analyse
                meteo_vars = [col for col in weather_data.columns 
                             if col not in ['date', 'month', 'localisation'] 
                             and any(x in col for x in ['dju', 'djf', 'temp', 'sun'])]
                
                # Ajouter à la liste des variables disponibles
                st.subheader("Variables disponibles pour l'analyse")
                st.info("Utilisez ces variables dans votre modèle IPMVP pour une analyse plus précise.")
                
                # Afficher les variables
                all_vars = selected_vars + [v for v in meteo_vars if v not in selected_vars]
                for var in all_vars:
                    st.write(f"- {var}")
            
            else:
                st.error("Impossible de récupérer les données météo. Vérifiez la localisation ou votre connexion internet.")
        
        # Terminer
        status_text.text("Analyse terminée!")
        progress_bar.progress(100)

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Développé avec ❤️ pour l'analyse IPMVP")
