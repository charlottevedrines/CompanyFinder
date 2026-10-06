import streamlit as st
import json

st.title("Quelles types d'entreprises t'intéressent en France?")


# Region du siege de l'entreprise 
region = st.selectbox(
    "Choisit ta région (siège de l'entreprise)",
    ["Île-de-France", "Provence-Alpes-Côte d'Azur", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France", "Grand Est", "Bretagne", "Normandie", "Pays de la Loire", "Centre-Val de Loire", "Bourgogne-Franche-Comté", "Corse"]
)

# Nombre d'employés de l'entreprise
employees = st.selectbox(
    "Choisit ta tranche d'effectif (siège de l'entreprise)",
    ["1 ou 2 salariés", 
    "3 à 5 salariés", 
    "6 à 9 salariés", 
    "10 à 19 salariés", 
    "20 à 49 salariés", 
    "50 à 99 salariés",
    "100 à 199 salariés",
    "200 à 249 salariés",
    "250 à 499 salariés",
    "500 à 999 salariés",
    "1 000 à 1 999 salariés",
    "2 000 à 4 999 salariés",
    "5 000 à 9 999 salariés",
    "10 000 salariés et plus"]
)



# Display the selections
st.write(f"You selected the region: **{region}**")
st.write(f"You selected the number of employees: **{employees}** ")

# Save selections to a JSON file
if st.button("Save selections"):
    data = {
        "region": region,
        "employees": employees
    }
    with open("selections.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    st.success("Saved to selections.json!")