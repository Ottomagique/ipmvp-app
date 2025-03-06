import requests
import pandas as pd
import streamlit as st
from datetime import datetime

class WeatherAPI:
    def __init__(self, api_key=None):
        # Utilisez votre clé API ou celle fournie en paramètre
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
