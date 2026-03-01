# DSBA-FavorableHousingParis

## About this project

### Description

Repository for MSc DSBA Data Vizualisation course. Topic is the definition of districts more and less favorable for student who search housing in Paris. Multiple criterion are tested such as commute time, rent price, surface, energy consumption...

Here are some examples of visuals produced for this project:

![rent](./visuals/paris_rent_map.png)

![furnished](./visuals/paris_furnished_map.png)

![commute](./visuals/paris_commute_map.png)

### Our Goal

As DSBA students, our goal is to help our student peers (regardless of their school and track) to find the right place to rent for their studies in and around Paris. Our motive is, if we had to start scholarship again, where would we want to live so we don't get home tired and pressured by expanses.

### Dataset used

* Logement - Encadrement des Loyers, OpenData Paris: [https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers/information/?utm_source=chatgpt.com&amp;disjunctive.nom_quartier&amp;disjunctive.piece&amp;disjunctive.epoque&amp;disjunctive.meuble_txt&amp;disjunctive.id_zone&amp;disjunctive.annee&amp;sort=-id_quartier](https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers/information/?utm_source=chatgpt.com&disjunctive.nom_quartier&disjunctive.piece&disjunctive.epoque&disjunctive.meuble_txt&disjunctive.id_zone&disjunctive.annee&sort=-id_quartier)
* Calculateur Ile-de-France - Isochrone v2: [https://prim.iledefrance-mobilites.fr/fr/apis/idfm-navitia-isochrones-v2](https://prim.iledefrance-mobilites.fr/fr/apis/idfm-navitia-isochrones-v2)

### Authors
- Marta SHKRELI
- Matteo COUCHOUD

## User Manual

To run our project, clone the repository on your computer, and put the *logement-encadrement-des-loyers.geojson* file in the geodata folder of the cloned repository. Then go to  *main* , and run the *main.ipynb* notebook file. **Having anaconda installed on your computer is required.**

The geojson file can be downloaded at this address [https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers](https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers/export/?disjunctive.nom_quartier&disjunctive.piece&disjunctive.epoque&disjunctive.meuble_txt&disjunctive.id_zone&disjunctive.annee&sort=-id_quartier&location=12,48.85889,2.34692&basemap=jawg.streets). Make sure to download it as a GeoJSON or the MVP will not work. This file wasn't included as to not clutter the Github repository.

