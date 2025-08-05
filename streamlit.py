import streamlit as st
import requests
import pandas as pd
import time

API_KEY = "S_JCKf5hL_eFroXJ61xeaQ"
SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/search"
ENRICH_URL = "https://api.apollo.io/api/v1/people/enrich"
ORG_URL = "https://api.apollo.io/api/v1/organizations/"

def get_org_location(org_id, headers):
    try:
        resp = requests.get(f"{ORG_URL}{org_id}", headers=headers)
        if resp.status_code == 200:
            org = resp.json().get("organization", {})
            location = org.get("location_name", "")
            if not location:
                city = org.get("city", "")
                state = org.get("state", "")
                country = org.get("country", "")
                if city and (state or country):
                    location = f"{city}, {state or country}"
            return location
    except Exception as e:
        st.warning(f"Error getting org location: {e}")
    return ""

def search_contacts(domain, designation, location="", limit=10):
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": API_KEY
    }

    params = {
        "q_organization_domains_list[]": domain.lower(),
        "person_titles[]": designation,
        "include_similar_titles": True,
        "page": 1,
        "per_page": limit
    }

    if location:
        formatted_location = location.strip()
        st.write(f"Using formatted location: `{formatted_location}`")
        params["person_locations[]"] = formatted_location
        params["organization_locations[]"] = formatted_location

    response = requests.post(SEARCH_URL, headers=headers, json={}, params=params)
    response.raise_for_status()
    people = response.json().get("people", [])

    results = []
    for person in people:
        first = person.get("first_name", "")
        last = person.get("last_name", "")
        title = person.get("title", "")
        org = person.get("organization", {}).get("name", "")
        org_id = person.get("organization", {}).get("id", "")
        linkedin = person.get("linkedin_url", "")
        email = person.get("email", "")

        location_info = (
            person.get("location", {}).get("name") or 
            person.get("location_name") or 
            (f"{person.get('city', '')}, {person.get('state', '')}" if person.get('city') and person.get('state') else "") or
            (f"{person.get('city', '')}, {person.get('country', '')}" if person.get('city') and person.get('country') else "") or
            (get_org_location(org_id, headers) if org_id else "")
        )
        if location_info == ", ":
            location_info = ""

        phone = []
        phone_source = "Individual"
        phone_numbers = person.get("phone_numbers", [])
        if phone_numbers:
            for phone_obj in phone_numbers:
                if isinstance(phone_obj, dict):
                    phone_number = phone_obj.get("sanitized_number") or phone_obj.get("number") or phone_obj.get("value")
                    if phone_number:
                        phone.append(phone_number)
                elif isinstance(phone_obj, str):
                    phone.append(phone_obj)

        # Enrich via LinkedIn
        if (not email or email.startswith("email_not_unlocked")) and linkedin:
            enrich_resp = requests.post(ENRICH_URL, headers=headers, json={"linkedin_url": linkedin})
            if enrich_resp.status_code == 200:
                enriched = enrich_resp.json().get("person", {})
                email = enriched.get("email", email)
                phone_numbers = enriched.get("phone_numbers", [])
                if phone_numbers and not phone:
                    for phone_obj in phone_numbers:
                        if isinstance(phone_obj, dict):
                            phone_number = phone_obj.get("sanitized_number") or phone_obj.get("number")
                            if phone_number:
                                phone.append(phone_number)

        # Enrich via name + org
        if (not email or email.startswith("email_not_unlocked")) and first and last and org:
            enrich_resp = requests.post(ENRICH_URL, headers=headers, json={
                "first_name": first,
                "last_name": last,
                "organization_name": org
            })
            if enrich_resp.status_code == 200:
                enriched = enrich_resp.json().get("person", {})
                email = enriched.get("email", email)
                phone_numbers = enriched.get("phone_numbers", [])
                if phone_numbers and not phone:
                    for phone_obj in phone_numbers:
                        if isinstance(phone_obj, dict):
                            phone_number = phone_obj.get("sanitized_number") or phone_obj.get("number")
                            if phone_number:
                                phone.append(phone_number)

        # Enrich via email only
        if not phone and email and not email.startswith("email_not_unlocked"):
            enrich_resp = requests.post(ENRICH_URL, headers=headers, json={"email": email})
            if enrich_resp.status_code == 200:
                enriched = enrich_resp.json().get("person", {})
                phone_numbers = enriched.get("phone_numbers", [])
                if phone_numbers:
                    for phone_obj in phone_numbers:
                        if isinstance(phone_obj, dict):
                            phone_number = phone_obj.get("sanitized_number") or phone_obj.get("number")
                            if phone_number:
                                phone.append(phone_number)

        # Fallback to org phone
        if not phone and person.get("organization", {}).get("primary_phone"):
            org_phone = person.get("organization", {}).get("primary_phone")
            if isinstance(org_phone, dict):
                phone_number = org_phone.get("sanitized_number") or org_phone.get("number")
                if phone_number:
                    phone.append(phone_number)
                    phone_source = "Company"
            elif isinstance(org_phone, str):
                phone.append(org_phone)
                phone_source = "Company"

        results.append({
            "FirstName": first,
            "LastName": last,
            "Position": title,
            "Email": email,
            "Phone": ", ".join(phone),
            "PhoneSource": phone_source,
            "Organization": org,
            "LinkedIn": linkedin,
            "Location": location_info
        })

        time.sleep(1)

    return results

# -------------------------
# STREAMLIT UI
# -------------------------

st.title("🔍 Contact Finder")

with st.form("search_form"):
    domain = st.text_input("🔍 Enter company domain (e.g. tcs.com)", "")
    designation = st.text_input("🎯 Enter a job title keyword (e.g. HR Manager)", "")
    location = st.text_input("🌍 Optional: Enter location (e.g. Mumbai or New York)", "")
    limit = st.number_input("🔢 How many results to return? (max 10)", min_value=1, max_value=10, value=5)
    submitted = st.form_submit_button("🚀 Find Contacts")

if submitted:
    if not domain or not designation:
        st.error("Please enter both domain and designation.")
    else:
        try:
            results = search_contacts(domain, designation, location, limit)
            if results:
                st.success(f"✅ Found {len(results)} people for '{designation}' at '{domain}'" + (f" in '{location}'" if location else "") + ":")
                df = pd.DataFrame(results)
                st.dataframe(df)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("⬇️ Download CSV", data=csv, file_name='contacts.csv', mime='text/csv')
            else:
                st.warning("❌ No matching people found.")
        except Exception as e:
            st.error(f"🚨 Error: {e}")

