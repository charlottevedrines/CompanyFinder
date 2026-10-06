import streamlit as st
import json

st.title("Quelles types d'entreprises t'intéressent ?")

# Pays du siege de l'entreprise 
pays = st.selectbox(
    "Choisit ton pays (siège de l'entrerpise)",
    ["France"]
)

# Region du siege de l'entreprise 
region = st.selectbox(
    "Choisit ta région (siège de l'entreprise)",
    ["Île-de-France", "Provence-Alpes-Côte d'Azur", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France", "Grand Est", "Bretagne", "Normandie", "Pays de la Loire", "Centre-Val de Loire", "Bourgogne-Franche-Comté", "Corse"]
)

# Secteur
secteur = st.selectbox(
    "Secteur",
    ["ESN"]
)

# Display the selections
st.write(f"You selected the country: **{pays}**")
st.write(f"You selected the region: **{region}**")
st.write(f"You selected the sector: **{secteur}** ")

# Save selections to a JSON file
if st.button("Save selections"):
    data = {
        "pays": pays,
        "region": region,
        "secteur": secteur
    }
    with open("selections.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    st.success("Saved to selections.json!")