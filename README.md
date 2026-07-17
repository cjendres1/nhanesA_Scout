This streamlit app [NHANES Scout](https://nhanes-scout.streamlit.app)
allows the user to search for NHANES tables and generate python code to import the selected tables.

USAGE:

1: Perform a search, which can either be a literal search or semantic search.
- Semantic search : Set the minimum similarity score to the desired level.
Enter search term(s), e.g. heart attack or heart attack, blood pressure.
The search terms will be compared to the variable descriptions, and matches with a similarity
score above the minimum threshold will be displayed. 

- Literal search : This operates like the nhanesSearch function in nhanesA. Only exact matches to the
search terms are returned. Note that the search is case insensitive. E.g. a search on diabetes will
match to Diabetes or diabetes, but will not match to diabetic. 

2: Select tables to download
- A checkbox indicates whether or not to include corresponding demographics tables.
- The identified tables can be selected/deselected as desired.

3: A python code snippet is created that will import all selected tables. The user simply needs to copy the code and run in python.
