import streamlit as st
import pydeck as pdk
import pandas as pd
import logging

import os.path
import re

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


@st.cache_data(ttl=3600)
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
        df = df.sort_values('Timestamp').groupby(['Branch Name', 'Pub Name']).tail(1).reset_index(drop=True)
        df = df.sort_values(['Pub State', 'Pub City']).reset_index(drop=True)
        return df
    except HttpError as err:
        print(err)


def main():
    df = get_data()
    df = df.rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'})
    df = df.astype({'latitude':'float','longitude':'float'})
    st.title('Arsenal America')

    row1_col1, row1_col2 = st.columns([.25,.25])

    state_options = list(set(df['Pub State']))
    state_options.sort()
    
    with row1_col1:
        STATE_SELECT = st.selectbox('If there is a branch in your state you can search for it below:',
            ["Please select"] + state_options,
            key='state_select'
        )
    with row1_col2:
        def reset():
            st.session_state.state_select = 'Please select'
        st.text('')
        st.text('')
        st.button('Reset', on_click=reset)

    # filter data based on selections
    all_states = STATE_SELECT == 'Please select'
    if not all_states:
        df = df[df['Pub State'] == STATE_SELECT].reset_index()  

    icon_data = {
        "url": "https://image-service.onefootball.com/transform?w=128&dpr=2&image=https://images.onefootball.com/icons/teams/164/2.png",
        "width": 64,
        "height": 64,
        "anchorY": 64
    }

    tooltip = {
        "html": "<b>Branch:</b> {Branch Name} <br/> <b>Pub:</b> {Pub Name}",
        "style": {
                "backgroundColor": "gray",
                "color": "white"
        }
    }

    df['icon_data'] = pd.Series([icon_data for x in range(len(df.index))])

    icon_layer = pdk.Layer(
        type="IconLayer",
        data=df,
        get_icon="icon_data",
        get_size=4,
        size_scale=15,
        get_position=["longitude", "latitude"],
        pickable=True
    )

    if all_states:
        view_state = pdk.ViewState(longitude=-98.5,latitude=38.500, zoom=3)
        # view_state = pdk.data_utils.compute_view(df[["longitude", "latitude"]], 1)
    else: 
        view_state = pdk.ViewState(
            longitude=(
                max(df['longitude']) - (
                    max(df['longitude']) - 
                    min(df['longitude'])
            )/2),
            latitude=max(df['latitude']), zoom=5
        )

    r = pdk.Deck(
        map_style=None,
        layers=[icon_layer],
        initial_view_state=view_state,
        tooltip=tooltip
    )
    st.pydeck_chart(r)

    states_df = df.groupby(by='Pub State')
    states = dict(list(states_df))
    for state in states:
        state_pubs_df = states_df.get_group(state)
        state_pubs_df = state_pubs_df.sort_values(by=['Branch Name', 'Pub City'])
        pubs = list(state_pubs_df['Pub Name'].tolist())
        pub_groups = zip(*(iter(pubs),) * 2) if len(pubs)>1 else [tuple(pubs)]

        with st.expander(state, not all_states):
            for group in pub_groups:
                col1, col2 = st.columns([1,1])
                cols = [col1, col2]
                for count, col in enumerate(cols):
                    pub = group[count] if len(group) >= count+1 else None
                    if pub:
                        with col:
                            pub_data = state_pubs_df[state_pubs_df['Pub Name']==pub].to_dict('records')[0]
                            st.subheader(pub_data['Branch Name'])
                            st.caption(pub)
                            pub_col1, pub_col2, pub_col3, _ = st.columns([1,1,1,5])
                            with pub_col1:
                                link_nav = re.sub(' ', '%20',
                                        'https://www.google.com/maps/search/' + '+'.join([
                                        pub_data.get('Pub Name'),
                                        pub_data.get('Pub Address 1'),
                                        pub_data.get('Pub City'),
                                        pub_data.get('Pub State'),
                                        pub_data.get('Pub ZIP Code'),
                                    ])
                                )
                                st.markdown(
                                        f'[<img src="./app/static/gmaps.png" height="21">]({link_nav})',
                                        unsafe_allow_html=True,
                                    )
                                st.text('')
                            with pub_col2:
                                link_fb = pub_data.get('Branch Facebook Page')
                                if link_fb:
                                    link_fb = re.sub(r'^.*?facebook', 'https://facebook', link_fb)
                                    st.markdown(
                                        f'[<img src="./app/static/fb.png" height="21">]({link_fb})',
                                        unsafe_allow_html=True,
                                    )
                                    st.text('')
                            with pub_col3:
                                link_twitter = pub_data.get('Branch Twitter Handle')
                                if link_twitter:
                                    link_twitter = f'https://twitter.com/{link_twitter}'
                                    st.markdown(
                                        f'[<img src="./app/static/twitter.png" height="21">]({link_twitter})',
                                        unsafe_allow_html=True,
                                    )
                                    st.text('')
                            # with pub_col2:
                            #     st.markdown("![Foo](http://www.google.com.au/images/nav_logo7.png)(http://google.com.au/)")
                            #     st.image(image=img_nav, width=14)


if __name__ == '__main__':
    main()