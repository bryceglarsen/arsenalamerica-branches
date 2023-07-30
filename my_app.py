import streamlit as st
import pandas as pd
import logging

import os.path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# from geopy.geocoders import Nominatim

# geolocator = Nominatim(user_agent="arsenalamerica-branches")

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

sheet_url = st.secrets["gsheets"]["private_gsheets_url"]
branches_sheet = 'FormResponses!A:Y'
coordinates_sheet = 'Coordinates!A:E'

def create_connection():
    credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], 
    scopes=["https://www.googleapis.com/auth/spreadsheets",],)
    return credentials


def write_data():
    ...


def get_data():
    creds = create_connection()

    try:
        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        # Call the Sheets API
        sheet = service.spreadsheets()
        branches = sheet.values().get(spreadsheetId="1aMm4dHHmzA2Xc8uWnpUaU_5xVjjAIGHltn7jXl-OIjc",
                                    range=branches_sheet).execute()
        branches_data = branches.get('values', [])
        coordinates = sheet.values().get(spreadsheetId="1aMm4dHHmzA2Xc8uWnpUaU_5xVjjAIGHltn7jXl-OIjc",
                                    range=coordinates_sheet).execute()
        coordinates_data = coordinates.get('values', [])

        if not branches_data or not coordinates_data:
            print('No data found.')
            return

        branches_df = pd.DataFrame(data=branches_data[1:], columns=branches_data[0])
        coordinates_df = pd.DataFrame(data=coordinates_data[1:], columns=coordinates_data[0])
        
        df = branches_df.merge(coordinates_df, how='inner', left_on=['Branch Name', 'Pub Name'], right_on=['Branch Name', 'Pub Name'])
        return df
    except HttpError as err:
        print(err)


def main():
    df = get_data()
    df = df.rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'})
    df = df.astype({'latitude':'float','longitude':'float'})
    st.title('Arsenal America')
    st.map(df, zoom=3)

    states_df = df.groupby(by='Pub State')
    states = dict(list(states_df))
    for state in states:
        state_pubs = states_df.get_group(state)
        cities = list(set(state_pubs['Pub City'].tolist()))
        cities.sort()
        with st.expander(state):
            for city in cities:
                st.write(city)


if __name__ == '__main__':
    main()