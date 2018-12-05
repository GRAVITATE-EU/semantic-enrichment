# GRAVITATE Semantic Enrichment Tool

Tool to process artifact free text descriptions and extract mentioned attribute properties. CIDOC-CRM predicates are generated in an RDF encoded format suitable for ingest into the GRAVITATE platform.

# Install

Copy the GRAVITATE semantic-enrichment release files to [install dir]

Unzip bm_lexicon.zip, ch-gazatteer.zip

Install Python 2.7 and Pip
Install Python lib NLTK 3.2.1 (download all corpus data)
Install Python lib Numpy 1.13.1+mk1
Install soton_corenlppy, lexicopy, openiepy

cd [install dir]
pip install --upgrade --upgrade-strategy “only-if-needed” soton_corenlppy-0.1.0-py27-none-any.whl
pip install --upgrade --upgrade-strategy “only-if-needed” lexicopy-0.1.0-py27-none-any.whl
pip install --upgrade --upgrade-strategy “only-if-needed” openiepy-0.1.0-py27-none-any.whl

Install R v3.4.4 >> C:\Program Files\R\R-3.4.4
Install Stanford POS tagger >> C:\stanford-parser-full
Install Stanford parser >> C:\stanford-postagger-full
Install Stanford english model >> C:\stanford-postagger-full\stanford-english-corenlp-2016-10-31-models.jar

Note: Installation of pre-requisites to other locations than specified will require edits to the file ch_information_extraction_app.ini

# Usage

Create your input data by running a SPARQL query against GRAVIATE BlazeGraph

curl -X POST http://localhost:9999/blazegraph/sparql --data-urlencode query@query-artifact-text.txt -H 'Accept:application/json;charset=UTF-8' -o "artifact-text.json"
Copy artifact-text.json to [install dir]
cd [install dir]
python ch_information_extraction_app.py ch_information_extraction_app.ini

The output file productions.trig will be generated in the <install dir>

# Contact

Admin: Stuart E. Middleton sem03[at]soton.ac.uk
