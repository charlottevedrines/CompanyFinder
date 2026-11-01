import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


'''
Summary:
This file fetched companies that are  NSEs (ESN in French) whose headquarters are in France. 
The companies are filtered by region and number of employees, which are selected in the interface.py file.
The output is written to a .json, which contains the filters used, the number of companies found, and a list of companies with their SIREN and name.

What is hardcoded:
- France: only french regions suggested and only french regions are mapped into a code for the API. In addition, is_company_in_france() checks that the company is in France. 
- ESN naf codes: hardcoded in get_naf_codes_for_sector()
Parameters:
- In find_companies() the number of companies is limited to 10 to avoid high API calls during prototype phase.
'''


API_URL = "https://recherche-entreprises.api.gouv.fr/search"


def get_selection_code(value, mapping, field_name):
    # An omitted or empty selection means no restriction.
    if value is None or value == "":
        return None

    # If value cannot be mapped then error message, this is to avoid values being mapped to smt not expected.
    if not isinstance(value, str) or value not in mapping:
        raise ValueError(
            f"Invalid {field_name}: {value!r}. "
            f"Expected one of: {', '.join(mapping)}"
        )

    return mapping[value]


def load_filters(path="selections.json"):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_naf_codes_for_sector(secteur):
    # Notre scope est limité aux ESN, les NAF codes sont hardcoded.
    # https://www.insee.fr/fr/information/8617910
    mapping = {
        "ESN": ["62.01Z", "62.02A", "62.02B", "62.03Z", "62.09Z"]
    }
    return mapping.get(secteur, [])


def is_company_in_region(company, region_code):
    siege = company.get("siege")
    if not isinstance(siege, dict) or not siege:
        return False
    
    if not region_code:
        return True
    return siege.get("region") == region_code


def company_nb_employees(company, employee_band):
    if not employee_band:
        return True

    # Company-wide employee band, not the headquarters' employee band.
    return company.get("tranche_effectif_salarie") == employee_band


def is_company_in_france(company):
    siege = company.get("siege") 
    if not isinstance(siege, dict) or not siege:
        print(f"Warning: Company {company.get('siren')} has no valid siege information.")
        return False
    
    # Si la boite est en France le champ "code_pays_etranger" devrait être vide et le champ "libelle_pays_etranger" devrait être vide aussi. 
    if siege.get("code_pays_etranger") is not None:
        return False
    if siege.get("libelle_pays_etranger"):
        return False
    return True


def matches_filters(filters, naf_codes, company):
    # etat_administratif = 'État administratif de l'établissement (A : Actif, F : Fermé)'
    if company.get("etat_administratif") != "A":
        return False

    # Si la boite n'est pas dans le secteur choisi, on ne la garde pas.
    if company.get("activite_principale") not in naf_codes:
        return False

    # Si la boite n'est pas dans en France, on ne la garde pas.
    if not is_company_in_france(company):
        return False
    
    # Si la boite n'est pas dans la région choisie, on ne la garde pas.
    if not is_company_in_region(company, map_region_name_to_code(filters.get("region"))):
        return False

    # Si la boite n'est pas dans la tranche d'effectif choisie, on ne la garde pas.
    if not company_nb_employees(company, map_employee_band_to_code(filters.get("employees"))):
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
    return get_selection_code(region_name, region_mapping, "region")


def map_employee_band_to_code(employee_band):
    # Les codes sont ceux renvoyés par l'API pour les tranches d'effectif.
    # Les codes sont détaillés ici, sous "Codes" 'https://entreprise.api.gouv.fr/catalogue/insee/unites_legales'
    employee_mapping = {
        "1 ou 2 salariés": "01",
        "3 à 5 salariés": "02",
        "6 à 9 salariés": "03",
        "10 à 19 salariés": "11",
        "20 à 49 salariés": "12",
        "50 à 99 salariés": "21",
        "100 à 199 salariés": "22",
        "200 à 249 salariés": "31",
        "250 à 499 salariés": "32",
        "500 à 999 salariés": "41",
        "1 000 à 1 999 salariés": "42",
        "2 000 à 4 999 salariés": "51",
        "5 000 à 9 999 salariés": "52",
        "10 000 salariés et plus": "53"
    }
    return get_selection_code(employee_band, employee_mapping, "employees")


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


def find_companies(filters, naf_codes, limit=10):
    ''' The loop continues until we have enough matches or we reach the maximum number of pages.
    This makes at most five API requests, examining up to 125 companies because per_page=25. 
    It stops earlier if it finds ten matches or reaches the last page.'''
    # Check if region and employee band are valid, error message if not.
    map_region_name_to_code(filters.get("region"))
    map_employee_band_to_code(filters.get("employees"))

    matches = []
    page = 1

    while len(matches) < limit :
        payload = fetch_page(naf_codes, page)
        results = payload.get("results", [])

        if not results:
            break

        for company in results:
            if matches_filters(filters, naf_codes, company):
                matches.append({
                    "siren": company["siren"],
                    "nom_raison_sociale": company.get("nom_raison_sociale"),
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

    secteur = "ESN"  # Hardcoded for now, as we are focusing on ESNs in France.
    naf_codes = get_naf_codes_for_sector(secteur)

    companies = find_companies(filters, naf_codes, limit=10)

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
        name = company.get("nom_raison_sociale") or company.get("nom_complet")
        print(f"{company['siren']} | {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
