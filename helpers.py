import pandas as pd
import numpy as np
import warnings
from openai import OpenAI
import time
import json
warnings.filterwarnings("ignore")

def load_city_country_analysis(combined_plot_summaries, data_path):
    # We load from movie_analysis.json and convert to df
    with open(data_path + '/movie_analysis.json', 'r') as f:
        analysis = json.load(f)
    
    # We convert the string in the values to a dict
    for key, value in analysis.items():
        analysis[key] = json.loads(value)
    
    def get_cities(one_analysis):
        if one_analysis is None:
            return []

        if 'cities' not in one_analysis:
            return []

        return one_analysis['cities']

    cities = [get_cities(value) for _, value in analysis.items()]
    cities = sorted(list(set([item for sublist in cities for item in sublist])))

    def get_countries(one_analysis):
        if one_analysis is None:
            return []

        if 'countries' not in one_analysis:
            return []

        return one_analysis['countries']

    countries = [get_countries(value) for _, value in analysis.items()]
    countries = sorted(list(set([item for sublist in countries for item in sublist])))
    
    cities_movies = {city: [] for city in cities}
    countries_movies = {country: [] for country in countries}

    for key, value in analysis.items():
        movie_cities = get_cities(value)
        movie_countries = get_countries(value)

        for city in movie_cities:
            if city in cities_movies:
                cities_movies[city].append(int(key))

        for country in movie_countries:
            if country in countries_movies:
                countries_movies[country].append(int(key))
                
    
    # Remove all countries with less than 10 movies both from countries and countries_movies
    countries = [country for country in countries if len(countries_movies[country]) >= 10]
    countries_movies = {country: countries_movies[country] for country in countries}
    
    # Remove all cities with less than 10 movies both from cities and cities_movies
    cities = [city for city in cities if len(cities_movies[city]) >= 10]
    cities_movies = {city: cities_movies[city] for city in cities}
    
    # These are corrections to the errors that ChatGPT made
    broken_countries = ['unknown', 'unspecified', 'None', 'Moon', '', 'Africa', 'fictional', 'Unknown']
    broken_cities = ['unknown', 'unspecified', 'None', 'Moon', '', 'village', 'town', 'small village', 'small town', 'remote village', 'hospital', 'fishing village', 'desert', 'countryside', 'city', 'big city', 'Unnamed City', 'Unknown', 'Town', 'Times Square',  'Small Town', 'Small town',  'Paradise',
                     'Gotham City', 'Europe', 'Earth', 'City', 'Atlantic City', 'Metropolis']

    countries_in_cities = ['Russia', 'Australia', 'Canada', 'United States', 'India', 'Iraq', 'New Zealand', 'Mexico', 'Jamaica', 'Japan', 'Italy', 'Panama', 'Rome', 'Singapore', 'Switzerland', 'Sweden', 'Spain','Germany', 'England', 'Egypt', 'China', 'Alexandria', 'America', 'France', 'Holland', 'Brazil', 'Vietnam', 'Greece', 'Thailand']
    cities_to_merge = [
        ['Washington D.C.', 'Washington', 'Washington DC', 'Washington, D.C.', 'Washington, DC'],
        ['Texas', 'Texas town'],
        ['New York', 'New York City'],
    ]


    # We will now remove all the broken countries and cities
    for country in broken_countries:
        if country in countries:
            countries.remove(country)
            del countries_movies[country]

    for city in broken_cities:
        if city in cities:
            cities.remove(city)
            del cities_movies[city]

    # We will now merge the cities that are in countries
    for country in countries_in_cities:
        if country in cities:
            if country not in countries:
                countries += [country]
                countries_movies[country] = []
            countries_movies[country] += cities_movies[country]
            countries_movies[country] = list(set(countries_movies[country]))
            del cities_movies[country]
            cities.remove(country)

    # We will now merge the cities that are in cities_to_merge
    for cities_to_merge_list in cities_to_merge:
        if cities_to_merge_list[0] in cities:
            for city in cities_to_merge_list[1:]:
                if city in cities:
                    cities_movies[cities_to_merge_list[0]] += cities_movies[city]
                    cities_movies[cities_to_merge_list[0]] = list(set(cities_movies[cities_to_merge_list[0]]))
                    del cities_movies[city]
                    cities.remove(city)

    embeddings_of_movies_in_cities = { city: [] for city in cities }
    embeddings_of_movies_in_countries = { country: [] for country in countries }

    for city_country in cities:
        embeddings_of_movies_in_cities[city_country] = np.array(combined_plot_summaries.loc[combined_plot_summaries['Wikipedia movie ID'].isin(cities_movies[city_country])]['embedding'].values.tolist())
    
    for city_country in countries:
        embeddings_of_movies_in_countries[city_country] = np.array(combined_plot_summaries.loc[combined_plot_summaries['Wikipedia movie ID'].isin(countries_movies[city_country])]['embedding'].values.tolist())

    return {
        'cities': cities,
        'countries': countries,
        'cities_movies': cities_movies,
        'countries_movies': countries_movies,
        'embeddings_of_movies_in_cities': embeddings_of_movies_in_cities,
        'embeddings_of_movies_in_countries': embeddings_of_movies_in_countries
    }
    
    
    
def load_data(data_path):
    """
    Does all data loading and preprocessing
    """
    character_metadata = pd.read_csv(data_path + 'MovieSummaries/character.metadata.tsv', 
                                 sep='\t', 
                                 names= [
                                     'Wikipedia movie ID',
                                     'Freebase movie ID',
                                     'Movie release date',
                                     'Character name',
                                     'Actor date of birth',
                                     'Actor gender',
                                     'Actor height (in meters)',
                                     'Actor ethnicity (Freebase ID)',
                                     'Actor name',
                                     'Actor age at movie release',
                                     'Freebase character/actor map ID',
                                     'Freebase character ID',
                                     'Freebase actor ID'
                                 ]
                                 )

    movie_metadata = pd.read_csv(data_path + 'MovieSummaries/movie.metadata.tsv', sep='\t', header=0,
                             names=['Wikipedia movie ID',
                                         'Freebase movie ID',
                                         'Movie name',
                                         'Movie release date',
                                         'Movie box office revenue',
                                         'Movie runtime',
                                         'Movie languages (Freebase ID:name tuples)',
                                         'Movie countries (Freebase ID:name tuples)',
                                         'Movie genres (Freebase ID:name tuples)'
                                         ])

    plot_summaries = pd.read_csv(data_path + 'MovieSummaries/plot_summaries.txt', sep='\t', names=[
        'Wikipedia movie ID',
        'Summary'
    ])
    
    # load the embeddings from disk
    embeddings = np.load(data_path + 'embeddings.npy', allow_pickle=True)
    embeddings_df = pd.DataFrame(embeddings, columns=['Wikipedia movie ID', 'embedding'])
    
    # Combine on the first column of embeddings
    combined_plot_summaries = pd.merge(plot_summaries, embeddings_df, on='Wikipedia movie ID')
    
    embeddings = np.array(embeddings[:,1].tolist())
    
    city_country_analysis = load_city_country_analysis(combined_plot_summaries, data_path)
    
    
    return {
        'character_metadata': character_metadata,
        'movie_metadata': movie_metadata,
        'plot_summaries': plot_summaries,
        'embeddings': embeddings,
        'combined_plot_summaries': combined_plot_summaries,
        'city_country_analysis': city_country_analysis
    }
    

client = OpenAI()
def get_embedding(text, model="text-embedding-ada-002"):
    """
    Get the embedding of a text using the OpenAI API
    """
    global client
    text = text.replace("\n", " ")
    text = text.replace("\t", " ")
    text = text.replace("\r", " ")
    text = text.replace("\x0b", " ")
    text = text.replace("\x0c", " ")
    try:
        embedding = client.embeddings.create(input=[text], model=model).data[0].embedding

        if embedding is None:
            print(f"Failed to process text: {text}. Error: embedding is None")
            return None
        return embedding
    except Exception as e:
        print(f"Failed to process text: {text}. Error: {str(e)}")
        time.sleep(60)
        return None