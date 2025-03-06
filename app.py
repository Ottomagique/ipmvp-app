import streamlit as st

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
            except Exception as e:
                st.error(f"Erreur d'authentification: {e}")
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

# Le reste de votre code d'application commence ici
# Titre de l'application
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
        'Date': pd.date_range(start='2023-01-01', periods=12, freq='M'),
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

# Section 2: Configuration des données météo
if proceed:
    # Section 3: Configuration du modèle
    st.sidebar.subheader("2. Configuration du modèle")
    
    # Nombre maximum de variables
    max_features = st.sidebar.slider("Nombre maximum de variables", 1, 4, min(4, len(selected_vars) if selected_vars else 1))
    
    # Bouton pour lancer l'analyse
    if st.sidebar.button("🚀 Lancer l'analyse IPMVP"):
        if not selected_vars:
            st.warning("Vous n'avez sélectionné aucune variable explicative. L'analyse risque de ne pas être pertinente.")
        
        st.subheader("Analyse IPMVP en cours...")
        
        # Dates min et max à partir des données
        start_date = df[date_col].min().strftime('%Y-%m-%d')
        end_date = df[date_col].max().strftime('%Y-%m-%d')
        
        st.write(f"Période analysée: du {start_date} au {end_date}")
        
        # Afficher la progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Préparation des données pour l'analyse
        X = df[selected_vars]
        y = df[conso_col]
        dates = df[date_col]
        
        # Création et entrainement du modèle IPMVP optimisé
        from optimized_model import OptimizedModelIPMVP
        
        status_text.text("Recherche du meilleur modèle... Priorité aux modèles simples")
        
        modele_ipmvp = OptimizedModelIPMVP()
        success = modele_ipmvp.trouver_meilleur_modele(
            X, y, max_features=max_features,
            progress_callback=lambda p: progress_bar.progress(p)
        )
        
        if success:
            status_text.text("Analyse terminée avec succès!")
            
            # Rapport
            rapport = modele_ipmvp.generer_rapport(y_original=y)
            st.subheader("Résultats de l'analyse IPMVP")
            st.text(rapport)
            
            # Visualisation
            st.subheader("Visualisation des résultats")
            results_df = modele_ipmvp.visualiser_resultats(X, y, dates=dates)
            
            # Afficher les graphiques
            st.image('resultats_modele_ipmvp.png')
            st.image('comparaison_consommations.png')
            
            # Téléchargement des résultats
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Données', index=False)
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

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Développé avec ❤️ pour l'analyse IPMVP")
