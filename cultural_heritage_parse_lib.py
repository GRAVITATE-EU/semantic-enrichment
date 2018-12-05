# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
..
	/////////////////////////////////////////////////////////////////////////
	//
	// (c) Copyright University of Southampton IT Innovation, 2016
	//
	// Copyright in this software belongs to IT Innovation Centre of
	// Gamma House, Enterprise Road, Southampton SO16 7NS, UK.
	//
	// This software may not be used, sold, licensed, transferred, copied
	// or reproduced in whole or in part in any manner or form or in or
	// on any media by any person other than in accordance with the terms
	// of the Licence Agreement supplied with the software, or otherwise
	// without the prior written consent of the copyright owners.
	//
	// This software is distributed WITHOUT ANY WARRANTY, without even the
	// implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
	// PURPOSE, except where stated in the Licence Agreement supplied with
	// the software.
	//
	// Created By : Stuart E. Middleton
	// Created Date : 2016/08/12
	// Created for Project: GRAVITATE
	//
	/////////////////////////////////////////////////////////////////////////
	//
	// Dependancies: None
	//
	/////////////////////////////////////////////////////////////////////////
	'''

Cultural heritage parsing functions

"""


import os, re, sys, copy, collections, codecs, string, ConfigParser, traceback, datetime, time, math, urllib
import nltk, nltk.stem.porter, nltk.corpus, numpy
import openiepy, lexicopy, cultural_heritage_patterns_regex

def get_cultural_heritage_config( **kwargs ) :
	"""
	return a cultural heritage config object for this specific set of languages. the config object contains an instantiated NLTK stemmer, tokenizer and settings tailored for the chosen language set. all available language specific corpus will be read into memory, such as street name variants. 
	cultural heritage config settings are below:

	| note: for a list of default config settings see common_parse_lib.get_common_config()
	| note: a config object approach is used, as opposed to a global variable, to allow geo_parse_lib functions to work in a multi-threaded environment

	:param kwargs: variable argument to override any default config values

	:return: configuration settings to be used by all cultural_heritage_parse_lib functions
	:rtype: dict
	"""

	# always use lower case for geoparse work as microblog references to locations do not follow nice camel case
	# note: do this before common_parse_lib.get_common_config() because we want things like stopwords and names to be lowercase for subsequent matching
	dictArgs = copy.copy( kwargs )

	# add in regex and POS labels for CH label types (e.g. catalogue index)
	# so the common_parse_lib tokenization and POS tagger function picks them up and uses them
	# note: remove NAMESPACE as the alpha_numeric pattern will pick this up (as some CH identifiers are very similar to namespace 123.A67)
	dictArgs['token_preservation_regex'] = [ ('regex_url','URI') ]
	for strLabelType in cultural_heritage_patterns_regex.dictTagPatterns :
		rePattern = cultural_heritage_patterns_regex.dictTagPatterns[strLabelType][0]
		strPOSLabel = cultural_heritage_patterns_regex.dictTagPatterns[strLabelType][1]
		dictArgs[strLabelType] = rePattern
		dictArgs['token_preservation_regex'].append( ( strLabelType, strPOSLabel ) )

	# setup common values
	dict_cultural_heritage_config = openiepy.openie_lib.get_openie_config( **dictArgs )

	# all done
	return dict_cultural_heritage_config

def generate_entity_node_name( namespace = None, entity_phrase = None, dict_ch_config = None ) :
	"""
	generate an entity name based on entity text (so it can be reused)

	:param unicode namespace: optional namespace (e.g. grav -> grav:node, or http://grav/ -> http://grav/node) 
	:param unicode entity_phrase: phrase of an extracted entity (e.g. red)
	:param dict dict_ch_config: config object returned from cultural_heritage_parse_lib.get_cultural_heritage_config()

	:return URL safe node name encoded using urllib.quote_plus()
	:rtype str
	"""

	# pretty print some characters so they are (a) valid RDF node names and (b) easier to read without %escape forms
	strEntityNode = entity_phrase.lower().strip().replace("'",'').replace('"','').replace('\n','').replace(' ','_').replace('.','_')

	# avoid very long names as some browsers cannot cope with > 2000 character URIs (and it makes things very ugly in TTL)
	if len(strEntityNode) > 1024 :
		strEntityNode = strEntityNode[:1024]

	# note encode as UTF8 otherwise urllib.quote_plus() will fail as it cannot handle unicode (it has ascii keys so we need UTF-8 encodable unicode)
	if namespace == None :
		return urllib.quote_plus( strEntityNode.encode('utf-8') )
	else :
		if namespace.startswith('<') :
			return namespace[:-1] + urllib.quote_plus( strEntityNode.encode('utf-8') ) + '>'
		else :
			return namespace + ':' + urllib.quote_plus( strEntityNode.encode('utf-8') )



def annotation_entity_CIDOC_CRM_RELIC( entity_phrase = None, entity_super_class = None, entity_lexicon_uri = None, entity_lexicon_schema = None, crm_thing_uri = None, extract_event_node = None, context_obj = None, check_wordnet = True, check_schema = True, entity_stemmer = None, dict_ch_config = None ) :
	"""
	generate context based on an entity extraction lookup in some semantic mapping tables. context is used in annotation_object_CIDOC_CRM() to assert annotation about a thing.

	the following semantic mapping strategy is employed
		* mapping table of known CH scheme types (e.g. ware) -> appropriate CIDOC-CRM nodes added to crm_thing
		* mapping table of known wordnet hypernyms (e.g. colour) -> appropriate CIDOC-CRM nodes added to crm_thing

	:param unicode entity_phrase: phrase of an extracted entity (e.g. black-figured shred)
	:param unicode entity_super_class: phrase of super class or head token (e.g. sherd) (optional can be None)
	:param unicode entity_lexicon_uri: URI to a lexicon concept (e.g. URI to a SKOS concept for Terracotta). None will disable schema mappings.
	:param unicode entity_lexicon_schema: URI to a lexicon schema (e.g. URI to a SKOS concept for Ware). None will disable schema mappings.
	:param unicode crm_thing_uri: URI of the thing the entity extraction came from (e.g. URI of an artifact whose physical description was parsed)
	:param unicode extract_event_node: node of the extract
	:param dict context_obj: context dict used to provide a consistent context in which entity is found and track previous decisions with regards things like object type assignment. sent_index and var_addr should be specified each iteration.
	:param bool check_wordnet: if True check wordnet mapping table
	:param bool check_schema: if True check wordnet mapping table
	:param nltk.stem.api.StemmerI entity_stemmer: NLTK stemmer, default is None
	:param dict dict_ch_config: config object returned from cultural_heritage_parse_lib.get_cultural_heritage_config()
	"""

	# check args without defaults
	if not isinstance( entity_phrase, (str,unicode) ) :
		raise Exception( 'invalid entity_phrase' )
	if not isinstance( entity_super_class, (str,unicode,type(None)) ) :
		raise Exception( 'invalid entity_super_class' )
	if not isinstance( entity_lexicon_uri, (str,unicode,type(None)) ) :
		raise Exception( 'invalid entity_lexicon_uri' )
	if not isinstance( entity_lexicon_schema, (str,unicode,type(None)) ) :
		raise Exception( 'invalid entity_lexicon_schema' )
	if not isinstance( crm_thing_uri, (str,unicode) ) :
		raise Exception( 'invalid crm_thing_uri' )
	if not isinstance( extract_event_node, (str,unicode) ) :
		raise Exception( 'invalid extract_event_node' )
	if not isinstance( context_obj, dict ) :
		raise Exception( 'invalid context_obj' )
	if not isinstance( check_wordnet, bool ) :
		raise Exception( 'invalid check_wordnet' )
	if not isinstance( check_schema, bool ) :
		raise Exception( 'invalid check_schema' )
	if not isinstance( entity_stemmer, (nltk.stem.api.StemmerI,type(None)) ) :
		raise Exception( 'invalid check_schema' )
	if not isinstance( dict_ch_config, dict ) :
		raise Exception( 'invalid dict_ch_config' )

	# check
	if not 'var_addr' in context_obj :
		raise Exception( 'context_obj expects variable address' )
	if not 'sent_index' in context_obj :
		raise Exception( 'context_obj expects sent index' )

	strEntityPhraseSafe = entity_phrase.lower().strip().replace('"','\\"').replace('\n','\\n')
	if entity_stemmer != None :
		strEntityPhraseSafe = entity_stemmer.stem( strEntityPhraseSafe )
	strEntityNode = generate_entity_node_name( namespace = None, entity_phrase = entity_phrase, dict_ch_config = dict_ch_config )
	if entity_stemmer != None :
		strEntityNode = entity_stemmer.stem( strEntityNode )

	if entity_super_class != None :
		strSuperEntityPhraseSafe = entity_super_class.lower().strip().replace('"','\\"').replace('\n','\\n')
		if entity_stemmer != None :
			strSuperEntityPhraseSafe = entity_stemmer.stem( strSuperEntityPhraseSafe )
		strSuperEntityNode = generate_entity_node_name( namespace = None, entity_phrase = entity_super_class, dict_ch_config = dict_ch_config )
		if entity_stemmer != None :
			strSuperEntityNode = entity_stemmer.stem( strSuperEntityNode )
	else :
		strSuperEntityPhraseSafe = None
		strSuperEntityNode = None


	#
	# mapping table for check for known schema (hard coded for now)
	#

	if (check_schema == True) and (entity_lexicon_schema != None) :

		# BM Ware (e.g. black-figured)
		# crm:thing crm:P2_has_type <http://collection.britishmuseum.org/id/thesauri/x24539>
		if entity_lexicon_schema == 'http://collection.britishmuseum.org/id/thesauri/ware' :
			if not 'object_ware' in context_obj :
				context_obj[ 'object_ware' ] = []
			context_obj[ 'object_ware' ].append( ( entity_lexicon_uri, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# BM Production (e.g. painted)
		# ann:prod_painted rdf:type crm:P12_Production
		# ann:prod_painted crm:P108_has_produced <http://collection.britishmuseum.org/id/object/GAA42933>
		# ann:prod_painted crm:P32_used_general_technique <http://collection.britishmuseum.org/id/thesauri/production/p>
		elif entity_lexicon_schema == 'http://collection.britishmuseum.org/id/thesauri/production' :
			if not 'object_production' in context_obj :
				context_obj[ 'object_production' ] = []
			context_obj[ 'object_production' ].append( ( entity_lexicon_uri, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# BM Object (e.g. sherd)
		# crm:thing crm:P2_has_type <http://collection.britishmuseum.org/id/thesauri/x24539>
		elif entity_lexicon_schema == 'http://collection.britishmuseum.org/id/thesauri/object' :
			if not 'object_type' in context_obj :
				context_obj[ 'object_type' ] = []
			context_obj[ 'object_type' ].append( ( entity_lexicon_uri, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )


	#
	# mapping table for wordnet hypernyms (hard coded for now)
	#

	if check_wordnet == True :

		# use head if we can for word lookup (to avoid adjectives etc that would always make a negative lookup in wordnet)
		strPhraseToLookup = entity_phrase
		if entity_super_class != None :
			strPhraseToLookup = entity_super_class

		# compile a list of noun hypernyms
		# setHyper = set([ <syn-name>.<lemma-name>, ... ])
		listSynsets = lexicopy.wordnet_lib.get_synset_names( strPhraseToLookup.lower().strip(), pos='n', dict_lexicon_config = dict_ch_config )
		setHyper = set([])
		setHyperDirect = set([])

		for syn in listSynsets :
			# add lemma for this term
			#lexicopy.wordnet_lib.get_lemma( set_lexicon = setHyper, syn = syn, lang = 'eng', dict_lexicon_config = dict_ch_config )

			# add lemma for all hypernyms of this term
			lexicopy.wordnet_lib.inherited_hypernyms( set_lexicon = setHyper, syn = syn, lang = 'eng', pos='n', max_depth=20, depth=0, dict_lexicon_config = dict_ch_config )

			# add lemma for all hypernyms of this term (direct only)
			lexicopy.wordnet_lib.inherited_hypernyms( set_lexicon = setHyperDirect, syn = syn, lang = 'eng', pos='n', max_depth=0, depth=0, dict_lexicon_config = dict_ch_config )

		#dict_ch_config['logger'].info( repr(setHyper) )

		# colours
		# <http://collection.britishmuseum.org/id/object/GAA42933> crm:P43_has_dimension grav:colour_red
		# grav:colour_red rdf:type crm:E54_Dimension
		# grav:colour_red crm:P2_has_type grav:colour_type
		# grav:colour_red crm:P90_has_value "red"
		# grav:colour_type rdf:type crm:E55_Type
		# grav:colour_type rdf:type skos:Concept
		# grav:colour_type rdfs:label "colour"
		if 'color.n.01.colour' in setHyper :
			if not 'object_colour' in context_obj :
				context_obj[ 'object_colour' ] = []
			context_obj[ 'object_colour' ].append( ( strEntityPhraseSafe, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# parts of a physical object (e.g. body part, fragment)
		# <http://collection.britishmuseum.org/id/object/GAA42933> crm:P56_bears_feature grav:feature_hand
		# grav:feature_hand rdf:type crm:E26_Physical_Feature
		# grav:feature_hand rdfs:label "hand"
		# TODO USE CHAP ONTOLOGY
		if ('part.n.02.part' in setHyper) or ('part.n.03.part' in setHyper) :
			if not 'object_part' in context_obj :
				context_obj[ 'object_part' ] = []
			context_obj[ 'object_part' ].append( ( strEntityPhraseSafe, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# decoration of a physical object (e.g. spiral)
		# <http://collection.britishmuseum.org/id/object/GAA42933> crm:P65_shows_visual_item grav:feature_spiral
		# grav:feature_spiral rdf:type crm:E36_Visual_Item
		# grav:feature_spiral rdfs:label "spiral"
		# TODO USE CHAP ONTOLOGY
		if 'decoration.n.01.decoration' in setHyper :
			if not 'object_decoration' in context_obj :
				context_obj[ 'object_decoration' ] = []
			context_obj[ 'object_decoration' ].append( ( strEntityPhraseSafe, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# symbols such as numbers and letters (e.g. alpha) or other symbols (direct hypernym only)
		if ('symbol.n.01.symbol' in setHyperDirect) or ('letter.n.01.letter' in setHyper) or ('number.n.02.number' in setHyper) :
			if not 'object_symbol' in context_obj :
				context_obj[ 'object_symbol' ] = []
			context_obj[ 'object_symbol' ].append( ( strEntityPhraseSafe, context_obj['var_addr'], context_obj['sent_index'], strEntityNode, extract_event_node, strSuperEntityPhraseSafe, strSuperEntityNode ) )

		# TODO use of context to get better mappings
		# add confidence values to these mappings somehow
		# 'painted' + lion/flower == high decoration confidence
		# 'painted' + red == high colour confidence
		# 'hand' + left == high confidence part
		# 'hawk-headed' + 'figure' != numeric figure (its a symboloic figure)

		# TODO look at size
		# and then the subject of size (e.g. small size, man-sized height)


def annotation_object_CIDOC_CRM_RELIC( crm_thing_uri = None, context_obj = {}, annotation_namespace = 'http://example.org/id/', include_prefix = True, dict_ch_config = None ) :
	"""
	generate turtle RDF annotations for object annotations given the full context gained after processing all extraction entities.
	this allows the best decisions to be made on global object assignments (e.g. which entity is the best guess of an object type)

	:param unicode crm_thing_uri: URI of the thing the entity extraction came from (e.g. URI of an artifact whose physical description was parsed)
	:param dict context_obj: context dict to provide context in which entity is found and track previous decisions with regards things like object type assignment
	:param unicode annotation_namespace: namespace for use when creating new CIDOC-CRM nodes (e.g. crm:E54_Dimension node for a colour entry)
	:param bool include_prefix: if True turtle prefixes will be included e.g. @prefix rdf: ...
	:param dict dict_ch_config: config object returned from cultural_heritage_parse_lib.get_cultural_heritage_config()

	:return: turtle encoded RDF annotations using CIDOC-CRM
	:rtype: unicode
	"""

	# check args without defaults
	if not isinstance( crm_thing_uri, (str,unicode) ) :
		raise Exception( 'invalid crm_thing_uri' )
	if not isinstance( context_obj, dict ) :
		raise Exception( 'invalid context_obj' )
	if not isinstance( annotation_namespace, (str,unicode) ) :
		raise Exception( 'invalid annotation_namespace' )
	if not isinstance( include_prefix, bool ) :
		raise Exception( 'invalid include_prefix' )
	if not isinstance( dict_ch_config, dict ) :
		raise Exception( 'invalid dict_ch_config' )

	# init
	listTurtle = []
	if include_prefix == True :
		listTurtle.append( '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .' )
		listTurtle.append( '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .' )
		listTurtle.append( '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .' )
		listTurtle.append( '@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .' )
		listTurtle.append( '@prefix ann: <' + annotation_namespace + '> .' )

	# ware
	if 'object_ware' in context_obj :
		# choose first mention of an object ware
		listEntities = context_obj['object_ware']
		if len(listEntities) > 0 :
			# sort by order of mention (sent_index then addr)
			listEntities = sorted( listEntities, key=lambda entry: entry[1] + entry[2]*1000, reverse=False )
			listTurtle.append( '<' + crm_thing_uri + '> crm:P2_has_type <' + listEntities[0][0] + '> .' )
			listTurtle.append( 'ann:' + listEntities[0][4] + ' crm:P141_assigned <' + listEntities[0][0] + '> .' )
			listTurtle.append( '' )

	# object type
	if 'object_type' in context_obj :
		# choose first mention of an object type
		listEntities = context_obj['object_type']
		if len(listEntities) > 0 :
			# sort by order of mention (sent_index then addr)
			listEntities = sorted( listEntities, key=lambda entry: entry[1] + entry[2]*1000, reverse=False )
			listTurtle.append( '<' + crm_thing_uri + '> crm:P2_has_type <' + listEntities[0][0] + '> .' )
			listTurtle.append( 'ann:' + listEntities[0][4] + ' crm:P141_assigned <' + listEntities[0][0] + '> .' )
			listTurtle.append( '' )

	# production
	if 'object_production' in context_obj :
		# choose all mentions of object production methods
		listEntities = context_obj['object_production']
		for entry in listEntities :
			listTurtle.append( 'ann:prod_' + entry[3] + ' rdf:type crm:P12_Production .' )
			listTurtle.append( '<' + crm_thing_uri + '> crm:P108i_was_produced_by ann:prod_' + entry[3] + ' .' )
			listTurtle.append( 'ann:' + entry[4] + ' crm:P141_assigned ann:prod_' + entry[3] + ' .' )
			listTurtle.append( 'ann:prod_' + entry[3] + ' crm:P108_has_produced <' + crm_thing_uri + '> .' )
			listTurtle.append( 'ann:prod_' + entry[3] + ' crm:P32_used_general_technique <' + entry[0] + '> .' )
		if len(listEntities) > 0 :
			listTurtle.append( '' )

	# colour
	if 'object_colour' in context_obj :
		# choose all mentions of object colour
		listEntities = context_obj['object_colour']
		for entry in listEntities :
			listTurtle.append( '<' + crm_thing_uri + '> crm:P43_has_dimension ann:colour_' + entry[3] + ' .' )
			listTurtle.append( 'ann:' + entry[4] + ' crm:P141_assigned ann:colour_' + entry[3] + ' .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' rdf:type crm:E54_Dimension .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' rdf:type skos:Concept .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' rdfs:label "' + entry[0] + '" .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' skos:prefLabel "' + entry[0] + '" .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' crm:P2_has_type ann:colour_type .' )
			listTurtle.append( 'ann:colour_' + entry[3] + ' crm:P90_has_value "' + entry[0] + '" .' )
			listTurtle.append( 'ann:colour_type rdf:type crm:E55_Type .' )
			listTurtle.append( 'ann:colour_type rdf:type skos:Concept .' )
			listTurtle.append( 'ann:colour_type rdfs:label "colour" .' )
			listTurtle.append( 'ann:colour_type skos:prefLabel "colour" .' )

			if entry[5] != None :
				listTurtle.append( 'ann:colour_' + entry[6] + ' rdf:type crm:E54_Dimension .' )
				listTurtle.append( 'ann:colour_' + entry[6] + ' rdf:type skos:Concept .' )
				listTurtle.append( 'ann:colour_' + entry[6] + ' rdfs:label "' + entry[5] + '" .' )
				listTurtle.append( 'ann:colour_' + entry[6] + ' skos:prefLabel "' + entry[5] + '" .' )
				listTurtle.append( 'ann:colour_' + entry[3] + ' skos:broader ann:colour_' + entry[6] + ' .' )

		if len(listEntities) > 0 :
			listTurtle.append( '' )

	# parts
	if 'object_part' in context_obj :
		# choose all mentions of object parts
		listEntities = context_obj['object_part']
		for entry in listEntities :
			listTurtle.append( '<' + crm_thing_uri + '> crm:P56_bears_feature ann:feature_' + entry[3] + ' .' )
			listTurtle.append( 'ann:' + entry[4] + ' crm:P141_assigned ann:feature_' + entry[3] + ' .' )
			listTurtle.append( 'ann:feature_' + entry[3] + ' rdf:type crm:E26_Physical_Feature .' )
			listTurtle.append( 'ann:feature_' + entry[3] + ' rdf:type skos:Concept .' )
			listTurtle.append( 'ann:feature_' + entry[3] + ' rdfs:label "' + entry[0] + '" .' )
			listTurtle.append( 'ann:feature_' + entry[3] + ' skos:prefLabel "' + entry[0] + '" .' )

			if entry[5] != None :
				listTurtle.append( 'ann:feature_' + entry[6] + ' rdf:type crm:E26_Physical_Feature .' )
				listTurtle.append( 'ann:feature_' + entry[6] + ' rdf:type skos:Concept .' )
				listTurtle.append( 'ann:feature_' + entry[6] + ' rdfs:label "' + entry[5] + '" .' )
				listTurtle.append( 'ann:feature_' + entry[6] + ' skos:prefLabel "' + entry[5] + '" .' )
				listTurtle.append( 'ann:feature_' + entry[3] + ' skos:broader ann:feature_' + entry[6] + ' .' )

		if len(listEntities) > 0 :
			listTurtle.append( '' )

	# symbols
	if 'object_symbol' in context_obj :
		# choose all mentions of object parts
		listEntities = context_obj['object_symbol']
		for entry in listEntities :
			listTurtle.append( '<' + crm_thing_uri + '> crm:P128_carries ann:symbol_' + entry[3] + ' .' )
			listTurtle.append( 'ann:' + entry[4] + ' crm:P141_assigned ann:symbol_' + entry[3] + ' .' )
			listTurtle.append( 'ann:symbol_' + entry[3] + ' rdf:type crm:E90_Symbolic_Object .' )
			listTurtle.append( 'ann:symbol_' + entry[3] + ' rdf:type skos:Concept .' )
			listTurtle.append( 'ann:symbol_' + entry[3] + ' rdfs:label "' + entry[0] + '" .' )
			listTurtle.append( 'ann:symbol_' + entry[3] + ' skos:prefLabel "' + entry[0] + '" .' )

			if entry[5] != None :
				listTurtle.append( 'ann:symbol_' + entry[6] + ' rdf:type crm:E90_Symbolic_Object .' )
				listTurtle.append( 'ann:symbol_' + entry[6] + ' rdf:type skos:Concept .' )
				listTurtle.append( 'ann:symbol_' + entry[6] + ' rdfs:label "' + entry[5] + '" .' )
				listTurtle.append( 'ann:symbol_' + entry[6] + ' skos:prefLabel "' + entry[5] + '" .' )
				listTurtle.append( 'ann:symbol_' + entry[3] + ' skos:broader ann:symbol_' + entry[6] + ' .' )

		if len(listEntities) > 0 :
			listTurtle.append( '' )

	# decorations
	if 'object_decoration' in context_obj :
		# choose all mentions of object parts
		listEntities = context_obj['object_decoration']
		for entry in listEntities :
			listTurtle.append( '<' + crm_thing_uri + '> crm:P65_shows_visual_item ann:decoration_' + entry[3] + ' .' )
			listTurtle.append( 'ann:' + entry[4] + ' crm:P141_assigned ann:decoration_' + entry[3] + ' .' )
			listTurtle.append( 'ann:decoration_' + entry[3] + ' rdf:type crm:E36_Visual_Item .' )
			listTurtle.append( 'ann:decoration_' + entry[3] + ' rdf:type skos:Concept .' )
			listTurtle.append( 'ann:decoration_' + entry[3] + ' rdfs:label "' + entry[0] + '" .' )
			listTurtle.append( 'ann:decoration_' + entry[3] + ' skos:prefLabel "' + entry[0] + '" .' )

			if entry[5] != None :
				listTurtle.append( 'ann:decoration_' + entry[6] + ' rdf:type crm:E36_Visual_Item .' )
				listTurtle.append( 'ann:decoration_' + entry[6] + ' rdf:type skos:Concept .' )
				listTurtle.append( 'ann:decoration_' + entry[6] + ' rdfs:label "' + entry[5] + '" .' )
				listTurtle.append( 'ann:decoration_' + entry[6] + ' skos:prefLabel "' + entry[5] + '" .' )
				listTurtle.append( 'ann:decoration_' + entry[3] + ' skos:broader ann:decoration_' + entry[6] + ' .' )

		if len(listEntities) > 0 :
			listTurtle.append( '' )

	# all done
	return '\n'.join( listTurtle )

def item_set_to_CIDOC_CRM_RDF( item_sets = [], annotation_namespace = 'http://example.org/id/', graph_namespace = None, include_prefix = True, entity_stemmer = None, dict_ch_config = None ) :
	"""
	generate turtle RDF annotations using CIDOC-CRM suitable for ResearchSpace from item sets created by add_item_sets_from_extraction() and its associated functions
	item sets are expected to include artifact_uri(...), rel_type(...), inferred_rel_type(...), obj(...), obj_head(...)

	:param list item_sets: list of item sets generated by extractions = [ [ 'rel_type(...)', 'subj_head(...)', 'artifact_uri(...)', ... ], ... ]
	:param unicode annotation_namespace: namespace for use when creating new CIDOC-CRM nodes (e.g. crm:E54_Dimension node for a colour entry)
	:param unicode graph_namespace: namespace for GRAPH (None for no graph)
	:param bool include_prefix: if True turtle prefixes will be included e.g. @prefix rdf: ...
	:param nltk.stem.api.StemmerI entity_stemmer: NLTK stemmer, default is None
	:param dict dict_ch_config: config object returned from cultural_heritage_parse_lib.get_cultural_heritage_config()

	:return: turtle encoded RDF annotations using CIDOC-CRM
	:rtype: unicode
	"""

	# check args without defaults
	if not isinstance( item_sets, list ) :
		raise Exception( 'invalid item_sets' )
	if not isinstance( annotation_namespace, (str,unicode) ) :
		raise Exception( 'invalid annotation_namespace' )
	if not isinstance( graph_namespace, (str,unicode,type(None)) ) :
		raise Exception( 'invalid graph_namespace' )
	if not isinstance( include_prefix, bool ) :
		raise Exception( 'invalid include_prefix' )
	if not isinstance( entity_stemmer, (nltk.stem.api.StemmerI,type(None)) ) :
		raise Exception( 'invalid check_schema' )
	if not isinstance( dict_ch_config, dict ) :
		raise Exception( 'invalid dict_ch_config' )

	# init
	listTurtle = []
	if include_prefix == True :
		listTurtle.append( '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .' )
		listTurtle.append( '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .' )
		listTurtle.append( '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .' )
		listTurtle.append( '@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .' )
		listTurtle.append( '@prefix ann: <' + annotation_namespace + '> .' )
	
	if graph_namespace != None :
		# note: BlazeGraph does not like the GRAPH keyword (its optional in SPARQL Trig spec)
		listTurtle.append( '<' + graph_namespace + '> {' )

	# group item sets by artifact_uri
	dictArtifact = {}
	for listItems in item_sets :
		strArtifactURI = None
		listObj = []
		listObjHead = []
		listSemanticType = []
		listSubj = []
		listSubjHead = []

		for strItem in listItems :

			# parse item sets of interest
			if strItem.startswith( 'artifact_uri(' ) and strItem.endswith( ')' ) :
				strArtifactURI = strItem[ len('artifact_uri(') : -1 ]
			elif strItem.startswith( 'obj(' ) and strItem.endswith( ')' ) :
				listObj.append( strItem[ len('obj(') : -1 ] )
			elif strItem.startswith( 'obj_head(' ) and strItem.endswith( ')' ) :
				listObjHead.append( strItem[ len('obj_head(') : -1 ] )
			elif strItem.startswith( 'semantic_type(' ) and strItem.endswith( ')' ) :
				listSemanticType.append( strItem[ len('semantic_type(') : -1 ] )
			elif strItem.startswith( 'inferred_semantic_type(' ) and strItem.endswith( ')' ) :
				listSemanticType.append( strItem[ len('inferred_semantic_type(') : -1 ] )
			elif strItem.startswith( 'subj(' ) and strItem.endswith( ')' ) :
				listSubj.append( strItem[ len('subj(') : -1 ] )
			elif strItem.startswith( 'subj_head(' ) and strItem.endswith( ')' ) :
				listSubjHead.append( strItem[ len('subj_head(') : -1 ] )

		# add to artifact entri
		if strArtifactURI == None :
			dict_ch_config['logger'].info( 'item set missing artifact URI (ignored) : ' + repr(listItems) )
			continue
		
		if not strArtifactURI in dictArtifact :
			dictArtifact[strArtifactURI] = []
		dictArtifact[strArtifactURI].append( [ listObj, listObjHead, listSemanticType, listSubj, listSubjHead ] )

	# create a NLP extraction event for each artifact
	nExtractionEventCount = 0

	listTurtle.append( 'ann:NLP_algorithm rdf:type crm:E39_Actor .' )

	listTurtle.append( 'ann:colour_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:colour_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:colour_type rdfs:label "colour" .' )
	listTurtle.append( 'ann:colour_type skos:prefLabel "colour" .' )

	listTurtle.append( 'ann:part_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:part_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:part_type rdfs:label "part" .' )
	listTurtle.append( 'ann:part_type skos:prefLabel "part" .' )

	listTurtle.append( 'ann:decoration_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:decoration_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:decoration_type rdfs:label "decoration" .' )
	listTurtle.append( 'ann:decoration_type skos:prefLabel "decoration" .' )

	listTurtle.append( 'ann:symbol_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:symbol_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:symbol_type rdfs:label "symbol" .' )
	listTurtle.append( 'ann:symbol_type skos:prefLabel "symbol" .' )

	listTurtle.append( 'ann:shape_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:shape_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:shape_type rdfs:label "shape" .' )
	listTurtle.append( 'ann:shape_type skos:prefLabel "shape" .' )

	listTurtle.append( 'ann:material_type rdf:type crm:E55_Type .' )
	listTurtle.append( 'ann:material_type rdf:type skos:Concept .' )
	listTurtle.append( 'ann:material_type rdfs:label "material" .' )
	listTurtle.append( 'ann:material_type skos:prefLabel "material" .' )


	for strURI in dictArtifact :
		nExtractionEventCount = nExtractionEventCount + 1

		#
		# <artifact> crm:P140i_was_attributed_by <extraction_event>
		#
		listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' rdf:type crm:E13_Attribute_Assignment .' )
		listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P140_assigned_attribute_to <' + strURI + '> .' )
		listTurtle.append( '<' + strURI + '> crm:P140i_was_attributed_by ann:extract_event' +  str(nExtractionEventCount) + ' .' )
		listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P14_carried_out_by ann:NLP_algorithm .' )

		# loop in each extraction
		for ( listObj, listObjHead, listSemanticType, listSubj, listSubjHead ) in dictArtifact[strURI] :

			# dict_ch_config['logger'].info( 'DUMP ITEM = ' + repr( (listSemanticType,listObj,listObjHead) ) )

			# make a set of entity nodes for each object phrase
			listObjEntities = []
			for strObj in listObj :
				strEntityNode = generate_entity_node_name( namespace = None, entity_phrase = strObj, dict_ch_config = dict_ch_config )
				if entity_stemmer != None :
					strEntityNode = entity_stemmer.stem( strEntityNode )
				listObjEntities.append( ( strEntityNode, strObj ) )

			# make a set of entity nodes for each object head (ignore head if it also appears in base)
			listObjHeadEntities = []
			for strObj in listObjHead :
				if not strObj in listObj :
					strEntityNode = generate_entity_node_name( namespace = None, entity_phrase = strObj, dict_ch_config = dict_ch_config )
					if entity_stemmer != None :
						strEntityNode = entity_stemmer.stem( strEntityNode )
					listObjHeadEntities.append( ( strEntityNode, strObj ) )

			# make a set of entity nodes for each subj phrase
			listSubjEntities = []
			for strSubj in listSubj :
				strEntityNode = generate_entity_node_name( namespace = None, entity_phrase = strSubj, dict_ch_config = dict_ch_config )
				if entity_stemmer != None :
					strEntityNode = entity_stemmer.stem( strEntityNode )
				listSubjEntities.append( ( strEntityNode, strSubj ) )

			# make a set of entity nodes for each subj head (ignore head if it also appears in base)
			listSubjHeadEntities = []
			for strSubj in listSubjHead :
				if not strSubj in listSubj :
					strEntityNode = generate_entity_node_name( namespace = None, entity_phrase = strSubj, dict_ch_config = dict_ch_config )
					if entity_stemmer != None :
						strEntityNode = entity_stemmer.stem( strEntityNode )
					listSubjHeadEntities.append( ( strEntityNode, strSubj ) )

			#
			# Part
			#
			if 'http://gravitate.org/id/relation/has_part_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:feature_' + strEntity + ' rdf:type crm:E26_Physical_Feature .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:feature_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P56_bears_feature ann:feature_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdf:type crm:E26_Physical_Feature .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:feature_' +strEntity + ' skos:broader ann:feature_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:feature_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:feature_' +strEntityHead + ' skos:broader ann:part_type .' )
					else :
							listTurtle.append( 'ann:feature_' +strEntity + ' skos:broader ann:part_type .' )

			if 'http://gravitate.org/id/relation/has_part_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:feature_' + strEntity + ' rdf:type crm:E26_Physical_Feature .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:feature_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:feature_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P56_bears_feature ann:feature_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdf:type crm:E26_Physical_Feature .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:feature_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:feature_' +strEntity + ' skos:broader ann:feature_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:feature_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:feature_' +strEntityHead + ' skos:broader ann:part_type .' )
					else :
							listTurtle.append( 'ann:feature_' +strEntity + ' skos:broader ann:part_type .' )


			#
			# Decoration
			#
			if 'http://gravitate.org/id/relation/is_decorated_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdf:type crm:E36_Visual_Item .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:decoration_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P65_shows_visual_item ann:decoration_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdf:type crm:E36_Visual_Item .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:decoration_' +strEntity + ' skos:broader ann:decoration_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:decoration_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:decoration_' +strEntityHead + ' skos:broader ann:decoration_type .' )
					else :
							listTurtle.append( 'ann:decoration_' +strEntity + ' skos:broader ann:decoration_type .' )

			if 'http://gravitate.org/id/relation/is_decorated_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdf:type crm:E36_Visual_Item .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:decoration_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:decoration_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P65_shows_visual_item ann:decoration_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdf:type crm:E36_Visual_Item .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:decoration_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:decoration_' +strEntity + ' skos:broader ann:decoration_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:decoration_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:decoration_' +strEntityHead + ' skos:broader ann:decoration_type .' )
					else :
							listTurtle.append( 'ann:decoration_' +strEntity + ' skos:broader ann:decoration_type .' )

			#
			# Colour
			#
			if 'http://gravitate.org/id/relation/has_colour_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:colour_' + strEntity + ' rdf:type crm:E54_Dimension .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' crm:P2_has_type ann:colour_type .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:colour_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P43_has_dimension ann:colour_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdf:type crm:E54_Dimension .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' crm:P2_has_type ann:colour_type .' )
							listTurtle.append( 'ann:colour_' +strEntity + ' skos:broader ann:colour_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:colour_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:colour_' +strEntityHead + ' skos:broader ann:colour_type .' )
					else :
							listTurtle.append( 'ann:colour_' +strEntity + ' skos:broader ann:colour_type .' )

			if 'http://gravitate.org/id/relation/has_colour_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:colour_' + strEntity + ' rdf:type crm:E54_Dimension .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:colour_' + strEntity + ' crm:P2_has_type ann:colour_type .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:colour_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P43_has_dimension ann:colour_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdf:type crm:E54_Dimension .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:colour_' + strEntityHead + ' crm:P2_has_type ann:colour_type .' )
							listTurtle.append( 'ann:colour_' +strEntity + ' skos:broader ann:colour_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:colour_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:colour_' +strEntityHead + ' skos:broader ann:colour_type .' )
					else :
							listTurtle.append( 'ann:colour_' +strEntity + ' skos:broader ann:colour_type .' )


			#
			# Symbol
			#

			if 'http://gravitate.org/id/relation/has_symbol_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdf:type crm:E90_Symbolic_Object .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:symbol_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P128_carries ann:symbol_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdf:type crm:E90_Symbolic_Object .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:symbol_' +strEntity + ' skos:broader ann:symbol_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:symbol_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:symbol_' +strEntityHead + ' skos:broader ann:symbol_type .' )
					else :
							listTurtle.append( 'ann:symbol_' +strEntity + ' skos:broader ann:symbol_type .' )

			if 'http://gravitate.org/id/relation/has_symbol_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdf:type crm:E90_Symbolic_Object .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:symbol_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:symbol_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P128_carries ann:symbol_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdf:type crm:E90_Symbolic_Object .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:symbol_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:symbol_' +strEntity + ' skos:broader ann:symbol_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:symbol_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:symbol_' +strEntityHead + ' skos:broader ann:symbol_type .' )
					else :
							listTurtle.append( 'ann:symbol_' +strEntity + ' skos:broader ann:symbol_type .' )

			#
			# Shape
			#
			if 'http://gravitate.org/id/relation/has_shape_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:shape_' + strEntity + ' rdf:type crm:E55_Type .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:shape_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdf:type crm:E55_Type .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:shape_' +strEntity + ' skos:broader ann:shape_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:shape_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:shape_' +strEntityHead + ' skos:broader ann:shape_type .' )
					else :
							listTurtle.append( 'ann:shape_' +strEntity + ' skos:broader ann:shape_type .' )

			if 'http://gravitate.org/id/relation/has_shape_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:shape_' + strEntity + ' rdf:type crm:E55_Type .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:shape_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:shape_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdf:type crm:E55_Type .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:shape_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:shape_' +strEntity + ' skos:broader ann:shape_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:shape_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:shape_' +strEntityHead + ' skos:broader ann:shape_type .' )
					else :
							listTurtle.append( 'ann:shape_' +strEntity + ' skos:broader ann:shape_type .' )

			#
			# Material
			#
			if 'http://gravitate.org/id/relation/made_of_material_obj' in listSemanticType :

				for (strEntity, strLabel) in listObjEntities :
					listTurtle.append( 'ann:material_' + strEntity + ' rdf:type crm:E57_Material .' )
					listTurtle.append( 'ann:material_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:material_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:material_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:material_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P45_consists_of ann:material_' + strEntity + ' .' )

					if len(listObjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listObjHeadEntities :
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdf:type crm:E26_Physical_Feature .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:material_' +strEntity + ' skos:broader ann:material_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:material_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:material_' +strEntityHead + ' skos:broader ann:part_type .' )
					else :
							listTurtle.append( 'ann:material_' +strEntity + ' skos:broader ann:part_type .' )

			if 'http://gravitate.org/id/relation/made_of_material_subj' in listSemanticType :

				for (strEntity, strLabel) in listSubjEntities :
					listTurtle.append( 'ann:material_' + strEntity + ' rdf:type crm:E57_Material .' )
					listTurtle.append( 'ann:material_' + strEntity + ' rdf:type skos:Concept .' )
					listTurtle.append( 'ann:material_' + strEntity + ' rdfs:label "' + strLabel + '" .' )
					listTurtle.append( 'ann:material_' + strEntity + ' skos:prefLabel "' + strLabel + '" .' )
					listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:material_' + strEntity + ' .' )
					listTurtle.append( '<' + strURI + '> crm:P45_consists_of ann:material_' + strEntity + ' .' )

					if len(listSubjHeadEntities) > 0 :
						for (strEntityHead, strLabelHead) in listSubjHeadEntities :
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdf:type crm:E26_Physical_Feature .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdf:type skos:Concept .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' rdfs:label "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:material_' + strEntityHead + ' skos:prefLabel "' + strLabelHead + '" .' )
							listTurtle.append( 'ann:material_' +strEntity + ' skos:broader ann:material_' + strEntityHead + ' .' )
							listTurtle.append( 'ann:extract_event' + str(nExtractionEventCount) + ' crm:P141_assigned ann:material_' + strEntityHead + ' .' )

							listTurtle.append( 'ann:material_' +strEntityHead + ' skos:broader ann:material_type .' )
					else :
							listTurtle.append( 'ann:material_' +strEntity + ' skos:broader ann:material_type .' )



	if graph_namespace != None :
		listTurtle.append( '}' )

	# all done
	return '\n'.join( listTurtle )
