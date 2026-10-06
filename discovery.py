import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

'''Ce fichier gère les entreprises dont le siège social est en France. À modifier si on veut gérer d'autres pays.'''

API_URL = "https://recherche-entreprises.api.gouv.fr/search"


# On garde les entreprises avec moins de 100 salariés.
# Les codes sont ceux renvoyés par l'API pour les tranches d'effectif.
# Les codes sont détaillés ici, sous "Codes" 'https://entreprise.api.gouv.fr/catalogue/insee/unites_legales'
UNDER_100_EMPLOYEE_BANDS = {"NN", "00", "01", "02", "03", "11", "12", "21"}


def load_filters(path="selections.json"):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def get_naf_codes_for_sector(secteur):
    mapping = {
        "ESN": ["62.01Z", "62.02A", "62.02B", "62.03Z", "62.09Z"]
    }
    return mapping.get(secteur, [])


def is_company_in_region(company, region_code):
    siege = company.get("siege") or {}
    if not region_code:
        return True
    return siege.get("region") == region_code

def is_company_in_country(company, country):

    siege = company.get("siege") or {}

    # Cas France : on regarde le champ "code_pays_etranger"
    if country == "France":
        if siege.get("code_pays_etranger") is not None:
            return False
        if siege.get("libelle_pays_etranger"):
            return False
        return True

    # Cas autre pays : ne verifie pas encore
    return True


def matches_filters(filters, naf_codes, company):
    # etat_administratif = 'État administratif de l'établissement (A : Actif, F : Fermé)'
    if company.get("etat_administratif") != "A":
        return False

    # Si la boite n'est pas dans le secteur choisi, on ne la garde pas.
    if company.get("activite_principale") not in naf_codes:
        return False

    # Si la boite n'est pas dans le pays choisi, on ne la garde pas.
    if not is_company_in_country(company, filters.get("pays")):
        return False
    
    # Si la boite n'est pas dans la région choisie, on ne la garde pas.
    if not is_company_in_region(company, map_region_name_to_code(filters.get("region"))):
        return False

    siege = company.get("siege") or {}
    band = siege.get("tranche_effectif_salarie")

    # Si la boite n'est pas dans la tranche d'effectif choisie, on ne la garde pas.
    if band not in UNDER_100_EMPLOYEE_BANDS:
        return False

    siren = company.get("siren")

    # On ne garde que les entreprises avec un SIREN valide et un nom.
    if not isinstance(siren, str) or len(siren) != 9 or not siren.isdigit():
        return False

    # On ne garde que les entreprises avec un nom.
    name = company.get("nom_raison_sociale") or company.get("nom_complet")
    if not name:
        return False

    return True

def map_region_name_to_code(region_name):
    region_mapping = {
        "Île-de-France": "11",
        "Provence-Alpes-Côte d'Azur": "93",
        "Auvergne-Rhône-Alpes": "84",
        "Nouvelle-Aquitaine": "75",
        "Occitanie": "76",
        "Hauts-de-France": "32",
        "Grand Est": "44",
        "Bretagne": "53",
        "Normandie": "28",
        "Pays de la Loire": "52",
        "Centre-Val de Loire": "24",
        "Bourgogne-Franche-Comté": "27",
        "Corse": "94"
    }
    return region_mapping.get(region_name)

def fetch_page(naf_codes, page_number):
    params = {
        "activite_principale": ",".join(naf_codes),
        "page": page_number,
        "per_page": 25,
        "minimal": "true",
        "include": "siege",
    }

    url = f"{API_URL}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SimpleCompanyDiscovery/1.0",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_top_companies(filters, naf_codes, limit=10):
    matches = []
    page = 1

    while len(matches) < limit:
        payload = fetch_page(naf_codes, page)
        results = payload.get("results", [])

        if not results:
            break

        for company in results:
            if matches_filters(filters, naf_codes, company):
                matches.append({
                    "siren": company["siren"],
                    "nom_entreprise": company.get("nom_raison_sociale"),
                    "nom_complet": company.get("nom_complet"),
                })

                if len(matches) >= limit:
                    return matches

        total_pages = payload.get("total_pages", page)
        if page >= total_pages:
            break

        page += 1

    return matches


def main():
    filters = load_filters()

    secteur = filters.get("secteur")
    naf_codes = get_naf_codes_for_sector(secteur)

    companies = find_top_companies(filters, naf_codes, limit=10)

    output = {
        "filters": filters,
        "count": len(companies),
        "companies": companies,
    }

    with open("matched_companies.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"{len(companies)} entreprises écrites dans matched_companies.json")
    for company in companies:
        print(f"{company['siren']} | {company['nom_entreprise']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
