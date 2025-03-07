import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import requests
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="Analyse IPMVP avec Météo",
    page_icon="📊",
    layout="wide"
)

# Fonction pour charger les données
@st.cache_data
def load_data(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier: {e}")
        return None

# Classe pour l'API météo
class WeatherAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or "ZE3U556AFCCFHBXSFC95XRABC"
        self.base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    
    def get_weather_data(self, location, start_date, end_date, bases_dju=[16, 18, 19], bases_djf=[22, 24, 26]):
        if ',' not in location and not (location.replace('.', '').replace('-', '').isdigit()):
            location = f"{location},FR"
            
        url = f"{self.base_url}/{location}/{start_date}/{end_date}"
        
        params = {
            'unitGroup': 'metric',
            'include': 'days',
            'key': self.api_key,
            'contentType': 'json'
        }
        
        try:
            with st.spinner(f"Récupération des données météo pour {location}..."):
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Traitement simplifié pour test
            daily_data = []
            for day in data.get('days', []):
                day_data = {
                    'date': day.get('datetime'),
                    'temp_mean': day.get('temp')
                }
                
                # Calculer DJU pour différentes bases
                for base in bases_dju:
                    day_data[f'dju_base_{base}'] = max(0, base - day.get('temp'))
                
                # Calculer DJF pour différentes bases
                for base in bases_djf:
                    day_data[f'djf_base_{base}'] = max(0, day.get('temp') - base)
                
                daily_data.append(day_data)
                
            # Convertir en DataFrame
            return pd.DataFrame(daily_data)
            
        except Exception as e:
            st.error(f"Erreur lors de la récupération des données météo: {str(e)}")
            return pd.DataFrame()

# Titre de l'application
st.title("📊 Analyse IPMVP avec Données Météo")
st.markdown("""
Cette application vous permet d'analyser vos données de consommation énergétique en les corrélant 
avec des données météorologiques récupérées automatiquement.
""")

# Barre latérale pour les paramètres
st.sidebar.header("Configuration")

# Section 1: Chargement des données
st.sidebar.subheader("1. Données de consommation")
uploaded_file = st.sidebar.file_uploader("Chargez votre fichier Excel de consommation", type=["xlsx", "xls"])

if uploaded_file is None:
    st.info("👆 Veuillez charger votre fichier Excel contenant les données de consommation.")
    
    # Exemple de données
    example_data = {
        'Date': pd.date_range(start='2023-01-01', periods=12, freq='ME'),
        'Consommation': [570, 467, 490, 424, 394, 350, 320, 310, 370, 420, 480, 540]
    }
    example_df = pd.DataFrame(example_data)
    
    st.write("Exemple de données attendues:")
    st.dataframe(example_df)
    
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
        var_options = [col for col in df.columns if col != date_col and col != conso_col]
        
        selected_vars = st.sidebar.multiselect(
            "Variables explicatives", 
            options=var_options,
            default=[col for col in var_options if 'dju' in str(col).lower()][:1]
        )
        
        proceed = True
    else:
        proceed = False

# Section 2: Données météo
if proceed:
    st.sidebar.subheader("2. Données météo")
    use_weather_api = st.sidebar.checkbox("Récupérer données météo", value=True)

    if use_weather_api:
        city = st.sidebar.text_input("Ville", "Paris")
        location = f"{city},FR"
        
        # Bases de température
        dju_base = st.sidebar.selectbox("Base DJU (°C)", [15, 16, 17, 18, 19, 20], index=3)  # 18°C par défaut
        djf_base = st.sidebar.selectbox("Base DJF (°C)", [20, 21, 22, 23, 24, 25], index=2)  # 22°C par défaut
        
        # Bouton pour récupérer les données météo
        if st.sidebar.button("Récupérer données météo"):
            start_date = df[date_col].min().strftime('%Y-%m-%d')
            end_date = df[date_col].max().strftime('%Y-%m-%d')
            
            st.write(f"Récupération des données météo pour {city} du {start_date} au {end_date}")
            
            # Initialiser l'API météo et récupérer les données
            weather_api = WeatherAPI()
            weather_data = weather_api.get_weather_data(
                location, 
                start_date, 
                end_date,
                bases_dju=[dju_base],
                bases_djf=[djf_base]
            )
            
            if not weather_data.empty:
                st.success(f"Données météo récupérées pour {city}")
                st.dataframe(weather_data)
