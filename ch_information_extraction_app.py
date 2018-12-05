# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
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
//    Created By :    Stuart E. Middleton
//    Created Date :    2017/06/05
//    Created for Project:    GRAVITATE
//
/////////////////////////////////////////////////////////////////////////
//
// Dependencies: None
//
/////////////////////////////////////////////////////////////////////////
"""

import os, sys, logging, traceback, codecs, datetime, copy, time, ast, math, re, random, shutil, json, csv, multiprocessing, subprocess
import soton_corenlppy, openiepy, lexicopy, nltk.stem
import cultural_heritage_parse_lib, cultural_heritage_patterns_regex

# TODO move semantic mapping (using association mining) to openie at end of project

'''
CH information extraction app
- use a CH training corpus + CH lexicon to train a set of open pattern templates
- filter open pattern templates based on statistically-based information gain metrics
- execute filtered open pattern templates to extract useful argument/relation/context information from CH test corpus 
'''

# regex for item set entries
# e.g. subj((phrase tokens)(head1)(head2)...)
regexItemSet = re.compile( ur'\A(?P<TYPE>[a-zA-z0-9]+)\(\((?P<PHRASE_LEXICON>[^)]+)\)(?P<HEAD>.*\))\)\Z', re.IGNORECASE | re.UNICODE )

# regex for association mining rules
regexAMRules = re.compile( ur'\A\"(?P<ITEMS>\{[^}]*\}) \=\> (?P<INFERENCE>\{[^}]*\})\"\Z', re.IGNORECASE | re.UNICODE )

def read_noun_type_ranked_list( filename = None, dict_openie_config = {} ) :

	readHandle = codecs.open( filename, 'r', 'utf-8', errors = 'replace' )
	listLines = readHandle.readlines()
	readHandle.close()

	listRankedNounType = []

	for strLine in listLines :
		if ( len(strLine) > 0 ) and (strLine[0] != '#') :
			listRankedNounType.append( strLine.strip() )
	
	return listRankedNounType

def add_item_sets_from_extraction( list_item_sets = None, list_extracted_prop = [], list_prop_pattern = [], list_head_terms = [], dict_openie_config = {} ) :
	#
	# take the attrib_ie proposition output and create compound item sets (one item per prop entry)
	# compound item set = subj((flint blades)(blade)), attr((of)(of)), ...
	#

	listItemSet = []
	for nIndexVar in range(len(list_prop_pattern)) :

		strVarType = list_prop_pattern[nIndexVar]
		strPhrase = list_extracted_prop[nIndexVar]

		strEntry = strVarType + '('

		strEntry = strEntry + '(' + soton_corenlppy.common_parse_lib.escape_token( strPhrase ) +')'

		listHeadTokens = list_head_terms[nIndexVar].split(' ')
		for strHead in listHeadTokens :
			strEntry = strEntry + '(' + soton_corenlppy.common_parse_lib.escape_token( strHead.lower() ) +')'

		strEntry = strEntry + ')'

		if not strEntry in listItemSet :
			listItemSet.append( strEntry )

	# add new item set to list of item sets
	if len(listItemSet) > 0 :
		list_item_sets.append( listItemSet )

def aggregate_phrases_in_item_set( list_item_sets = [], agg_patterns = [ ('attr',), ('attrbase','attrprep'), ('attrnoobjnosubj',) ], agg_var_name = 'attribute', dict_openie_config = {} ) :

	#
	# aggregate compound item sets, adding an extra attribute(...) entry to the item set
	# e.g. attrbase + attrprep -> attribute
	# e.g. attr -> attribute
	# compound item set = subj((flint blades)(blade)), attr((of)(of)), ...
	#

	for nIndexItemSet in range(len(list_item_sets)) :

		# get item set and make a copy for iteration (cannot iterate on a set and change its value)
		listItemSet = list_item_sets[nIndexItemSet]

		for tupleAggPattern in agg_patterns :
			listAggPhrase = []
			listAggHead = []

			for strTargetVar in tupleAggPattern :

				for strItem in list_item_sets[nIndexItemSet] :
					if strItem.startswith( strTargetVar + '(' ) :

						#
						# parse each compound item and break it apart
						#

						matchObj = regexItemSet.match( strItem )
						if matchObj != None :
							if 'TYPE' in matchObj.groupdict() :
								strVarType = matchObj.groupdict()['TYPE']

							else :
								raise Exception( 'type missing in item set : ' + repr(strItem) )

							if 'PHRASE_LEXICON' in matchObj.groupdict() :
								strVarPhrase = matchObj.groupdict()['PHRASE_LEXICON']
								if strVarPhrase != None :
									listTokensArg = strVarPhrase.lower().split(' ')
								else :
									listTokensArg = []
							else :
								raise Exception( 'head missing in item set : ' + repr(strItem) )

							if 'HEAD' in matchObj.groupdict() :
								strVarHead = matchObj.groupdict()['HEAD']
								if strVarHead != None :
									# get list of head terms from (head1)(head2) ...
									strVarHead = strVarHead.replace('(',' ')
									strVarHead = strVarHead.replace(')',' ')
									listHeadTokensArg = strVarHead.lower().split(' ')
									while '' in listHeadTokensArg :
										listHeadTokensArg.remove('')
								else :
									listHeadTokensArg = []

							else :
								raise Exception( 'head missing in item set : ' + repr(strItem) )

						else :
							raise Exception( 'bad parse of item set : ' + repr(strItem) )


						listAggPhrase.append( strVarPhrase )

						for strHead in listHeadTokensArg :
							if len(strHead) > 0 :
								if not strHead in listAggHead :
									listAggHead.append( strHead )

			# add aggregated phrase and head to item set
			if len(listAggPhrase) > 0 :
				strEntry = agg_var_name + '('

				strAggregatePhrase = ' '.join( listAggPhrase )
				strEntry = strEntry + '(' + strAggregatePhrase + ')'

				for strAggregateHead in listAggHead :
					strEntry = strEntry + '(' + strAggregateHead + ')'

				strEntry = strEntry + ')'

				if not strEntry in listItemSet :
					listItemSet.append( strEntry )

def expand_compound_items_and_apply_lexicon_schema_mappings( list_item_sets = [], lex_phrase_index = {}, lex_uri_index = {}, schema_ranked_list = {}, allow_non_ranked_schema = False, stemmer = None, dict_openie_config = {} ) :

	#
	# expand compound item sets into single value items suitable for association mining
	# also do a lexicon lexicon lookup for subj() and obj() types, assigning them a type classifications if they appear in a lexicon
	# e.g. subj((flint blade)(blade)) ==> subj(flint blade), subj_head(blade), subj_type(...)
	# single value item set = subj(flint blade), subj_head(blade), subj_type(...)
	#

	for nIndexItemSet in range(len(list_item_sets)) :

		# get item set and make a copy for iteration (cannot iterate on a set and change its value)
		listItemSet = list_item_sets[nIndexItemSet]
		listItemSetNew = []

		# lookup subject phrase schema type in lexicon
		for nIndexItem in range(len(listItemSet)) :
			strItem = listItemSet[nIndexItem]

			if strItem.startswith('artifact_uri(') :
					strVarType = 'artifact_uri'
					strVarPhrase = strItem[len(strVarType)+1:-1]
					listHeadTokensArg = []

			else :

				#
				# parse each compound item and break it apart
				#

				matchObj = regexItemSet.match( strItem )
				if matchObj != None :
					if 'TYPE' in matchObj.groupdict() :
						strVarType = matchObj.groupdict()['TYPE']

					else :
						raise Exception( 'type missing in item set : ' + repr(strItem) )

					if 'PHRASE_LEXICON' in matchObj.groupdict() :
						strVarPhrase = matchObj.groupdict()['PHRASE_LEXICON']
						if strVarPhrase != None :
							listTokensArg = strVarPhrase.lower().split(' ')
						else :
							listTokensArg = []
					else :
						raise Exception( 'head missing in item set : ' + repr(strItem) )

					if 'HEAD' in matchObj.groupdict() :
						strVarHead = matchObj.groupdict()['HEAD']
						if strVarHead != None :
							# get list of head terms from (head1)(head2) ...
							strVarHead = strVarHead.replace('(',' ')
							strVarHead = strVarHead.replace(')',' ')
							listHeadTokensArg = strVarHead.lower().split(' ')
							while '' in listHeadTokensArg :
								listHeadTokensArg.remove('')
						else :
							listHeadTokensArg = []

					else :
						raise Exception( 'head missing in item set : ' + repr(strItem) )

				else :
					raise Exception( 'bad parse of item set : ' + repr(strItem) )

			#
			# add components back as individual items
			#

			strEntry = strVarType + '(' + strVarPhrase + ')'
			if not strEntry in listItemSetNew :
				listItemSetNew.append( strEntry )

			for strHead in listHeadTokensArg :
				strEntry = strVarType + '_head(' + strHead + ')'
				if not strEntry in listItemSetNew :
					listItemSetNew.append( strEntry )

			#
			# for subject and object do a lexicon lookup
			#

			# get subj and obj vars (if any)
			if strVarType in ['subj','obj'] :

				listLexiconMatch = []

				if stemmer != None :
					for nIndex in range(len(listTokensArg)) :
						listTokensArg[nIndex] = stemmer.stem( listTokensArg[nIndex] )
					for nIndex in range(len(listHeadTokensArg)) :
						listHeadTokensArg[nIndex] = stemmer.stem( listHeadTokensArg[nIndex] )

				nVarGramSize = len(listTokensArg)

				#if strHeadTokenArg == 'flint' :
				#	dict_openie_config['logger'].info( 'flint = ' + repr( listTokensArg ) )

				if len(listTokensArg) > 0  :

					# do a lexicon lookup for all head tokens (there might be more than one for a long phrase than spans dep graph branches)
					for strHeadToken in listHeadTokensArg :

						# match lexicon to phrase ngrams
						# listLexiconMatch = [ ( lexicon_uri, schema_uri, matched_phrase, match_gram_size, confidence_score ), ... ]
						listLexiconMatch = lexicopy.lexicon_lib.phrase_lookup(
							phrase_tokens = listTokensArg,
							head_token = strHeadToken,
							lex_phrase_index = lex_phrase_index,
							lex_uri_index = lex_uri_index,
							max_gram = 5,
							stemmer = stemmer,
							apply_wordnet_morphy = True,
							hyphen_variant = True,
							dict_lexicon_config = dict_openie_config )

						#dict_openie_config['logger'].info( 'PHRASE LOOKUP = ' + repr( listTokensArg ) )

						# remove all but the highest confidence score results
						# get top confidence value
						nBestScore = None
						for nIndex in range(len(listLexiconMatch)) :
							if (nBestScore == None) or (listLexiconMatch[nIndex][4] > nBestScore) :
								nBestScore = listLexiconMatch[nIndex][4]

						# filter out anything with less than the top confidence score
						nIndex = 0
						while nIndex < len(listLexiconMatch) :
							if listLexiconMatch[nIndex][4] < nBestScore :
								del listLexiconMatch[nIndex]
							else :
								nIndex = nIndex + 1

						if len(listLexiconMatch) == 0 :
							continue

						# pick the most likely schema from a ranked list of schema
						# this list is ranked in order of how likely an occurance of each schema wordsense is for this domain
						strSchemaChoice = None
						for strSchema in schema_ranked_list :
							for ( lexicon_uri, schema_uri, matched_phrase, match_gram_size, confidence_score ) in listLexiconMatch :
								if strSchema == schema_uri :
									strSchemaChoice = strSchema
									break
							if strSchemaChoice != None :
								break

						# if the schema does not appear in our domain ranked list then just pick the first one as a 'guess'
						if (strSchemaChoice == None) and (allow_non_ranked_schema == True) :
							strSchemaChoice = listLexiconMatch[0][1]

						if strSchemaChoice == None :
							continue

						# add lexicon type to item set
						strEntry = strVarType + '_type(' + soton_corenlppy.common_parse_lib.escape_token(strSchemaChoice) + ')'
						if not strEntry in listItemSetNew :
							listItemSetNew.append( strEntry )

		# change original item set to be new one
		list_item_sets[nIndexItemSet] = listItemSetNew


def load_semantic_mapping( filename_mapping = None, dict_openie_config = {} ) :

	#
	# apply a semantic mapping (using a manual mapping table)
	# mapping in format item(...) <tab> item(...) <tab> ... attribute_type(schema)
	#

	listPatterns = []

	# tab delimited CSV for lemma
	readHandle = codecs.open( filename_mapping, 'rb', 'utf-8', errors = 'replace' )

	# we expect headers so ignore any line that starts with a #
	# note: do not use python csv classes as they do not work well with UTF-8 in the upper bound (e.g. japanese characters)
	strLine = '#'
	while len(strLine) > 0 :
		strLine = readHandle.readline()

		# EOF
		if len(strLine) == 0 :
			break

		# header
		if strLine.startswith('#') == True :
			continue

		# remove newline at end and ignore empty lines (e.g. at end of file)
		strLine = strLine.strip( '\r\n' )
		if len(strLine) > 0 :

			listItems = strLine.split('\t')
			if len( listItems ) < 2 :
				raise Exception( 'semantic mapping found with ' + str(len(listItems)) + ' items (min 2) : ' + repr(strLine) )
			if ( not listItems[-1].startswith( 'rel_type(' ) ) and ( not listItems[-1].endswith( ')' ) ):
				raise Exception( 'semantic mapping does not have rel_type(...) as last item : ' + repr(strLine) )

			listPatterns.append( listItems )
		else :
			strLine = '#'

	readHandle.close()

	# sort item patterns so ones with most items appear first
	listPatterns = sorted( listPatterns, key=lambda entry: len(entry), reverse=True )

	# return list
	return listPatterns

def apply_semantic_mapping_to_item_sets( list_item_sets = None, list_semantic_mapping = [], dict_openie_config = {} ) :

	if list_item_sets == None :
		return

	if list_semantic_mapping == None :
		return

	for listItemSet in list_item_sets :
		setItems = set( listItemSet )

		# assign the first pattern to match in the strict order specified in the list
		for listItemPattern in list_semantic_mapping :
			setPattern = set( listItemPattern[0:-1] )
			strRelType = listItemPattern[-1]

			if setPattern.issubset( setItems ) :
				# we have an item set pattern match so assign this rel_type(...) to the itemset
				listItemSet.append( strRelType )
				break

	# all done (list_item_sets modified to have schema assignments added as extra items)
	return

def apply_wordnet_mapping_to_item_sets( list_item_sets = None, allowed_types = set(['attribute_head', 'subj_head', 'obj_head']), count_freq_threshold = 0.5, top_n_lemma = 5, dict_openie_config = {} ) :

	if list_item_sets == None :
		return

	# loop on all attr_head(...) entries and add wordnet similar verbs
	for listItemSet in list_item_sets :
		for strItem in listItemSet :
			bAllowed = False
			strPOSFilter = None
			strWNType = None
			strPrefix = None
			for strType in allowed_types :
				if strItem.startswith(strType + '(') and strItem.endswith(')') == True :
					bAllowed = True
					strPOSFilter = None
					strPrefix = strType + '('
					listType = strType.split('_')
					if len(listType) != 2 :
						raise Exception( 'invalid allowed type : ' + strType )

					# limit wordsense: default = verb, subj/obj = noun
					# note: wordnet does not contain prepositions, just adjectives, adverbs, verbs and nouns
					strWNType = listType[0] + '_wn'
					if listType[0] in ['obj','subj'] :
						strPOSFilter = 'n'
					else :
						strPOSFilter = 'v'
					break

			if bAllowed :
				strPhraseToLookup = strItem[ len(strPrefix) : -1 ].lower().strip()
				setWordNet = set([])

				#if strPhraseToLookup == 'flint' :
				#	dict_openie_config['logger'].info('flint wordnet')

				# get all synsets
				listSynsets = lexicopy.wordnet_lib.get_synset_names(
					lemma = strPhraseToLookup,
					pos=strPOSFilter,
					dict_lexicon_config = dict_openie_config )

				# get all lemma and sort them by wordnet frequency count
				setLemmaWithFreq = set([])
				for syn in listSynsets :
					# get lemma
					lexicopy.wordnet_lib.get_lemma_with_freq(
						set_lexicon = setLemmaWithFreq,
						syn = syn,
						lang = 'eng',
						pos=strPOSFilter,
						dict_lexicon_config = dict_openie_config )

				# phrase not in wordnet?
				if len(setLemmaWithFreq) == 0 :
					continue

				# sort lemma in frequency order
				listLemmaWithFreq = list( setLemmaWithFreq )
				listLemmaWithFreq = sorted( listLemmaWithFreq, key=lambda entry: entry[1], reverse=True )

				#if strPhraseToLookup == 'flint' :
				#	dict_openie_config['logger'].info( 'flint wordnet = ' + repr(setLemmaWithFreq) )

				# apply top N filter to lemma to avoid spamming out wordnet entries later (which will slow up association mining)
				if top_n_lemma != None :
					listLemmaWithFreq = listLemmaWithFreq[:top_n_lemma]

				# disambiguate verb wordsense using wordnet corpus occurance frequency (as we have no other context to work with)
				# select lemma with a freq of N% of the most frequent sense, to capture those wordsenses that are statistically most likly and avoid the more obscure wordsenses
				nFreqTop = listLemmaWithFreq[0][1]
				nFreqThreshold = nFreqTop * count_freq_threshold
				if nFreqThreshold < 1 :
					nFreqThreshold = 1.0

				#if strPhraseToLookup == 'flint' :
				#	dict_openie_config['logger'].info( 'flint threshold = ' + repr(nFreqThreshold) )

				for ( strLemmaID, nFreqLemma ) in listLemmaWithFreq :
					# ignore?
					if nFreqLemma < nFreqThreshold :
						continue

					setWordNet.add( strLemmaID )

					# get wordnet syn object for it
					listParts = strLemmaID.split('.')
					if len(listParts) < 4 :
						raise Exception( 'invalid wordnet entry' )
					strSyn = '.'.join( listParts[0:3] )
					syn = lexicopy.wordnet_lib.get_synset(
						wordnet_synset_name = strSyn,
						dict_lexicon_config = dict_openie_config )

					# add hypernyms (verb = troponym, noun = hypernymn)
					lexicopy.wordnet_lib.inherited_hypernyms(
						set_lexicon = setWordNet,
						syn = syn,
						lang = 'eng',
						pos=strPOSFilter,
						max_depth=10,
						depth=0,
						dict_lexicon_config = dict_openie_config )

					# add verb groups
					lexicopy.wordnet_lib.verb_groups(
						set_lexicon = setWordNet,
						syn = syn,
						lang = 'eng',
						pos=strPOSFilter,
						dict_lexicon_config = dict_openie_config )

				#if strPhraseToLookup == 'flint' :
				#	dict_openie_config['logger'].info( 'flint words = ' + repr(setWordNet) )

				# add synset of all verb, hyponyms and verb groups
				setBase = set([])
				for strEntry in setWordNet :
					listParts = strEntry.split('.')
					if len(listParts) < 3 :
						raise Exception( 'invalid wordnet entry' )
					# setBase.add( '.'.join( listParts[0:3] ) )
					setBase.add( listParts[0] )

				#if strPhraseToLookup == 'flint' :
				#	dict_openie_config['logger'].info( 'flint base = ' + repr(setBase) )
				
				# add as item set entry (e.g. for association mining to make use of it)
				for strBase in setBase :
					strEntry = strWNType + '(' + strBase + ')'
					if not strEntry in listItemSet :
						listItemSet.append( strEntry )

	# all done (list_item_sets modified)
	return

def filter_item_sets( list_item_sets = None, mandatory_items = set([]), allowed_items = set(['attribute_head', 'subj_head', 'obj_head', 'attribute_wn', 'subj_wn', 'obj_wn']), remove_duplicates = True,  dict_openie_config = {} ) :

	if list_item_sets == None :
		return

	# make a copy of the original list
	listItemSetFiltered = copy.deepcopy( list_item_sets )

	# loop on each item set
	nIndexItemSet = 0
	while len(listItemSetFiltered) > nIndexItemSet :

		# check for mandatory items
		bReject = False
		for strItemMandatory in mandatory_items :
			bFound = False
			for strItem in listItemSetFiltered[nIndexItemSet] :
				if strItem.startswith( strItemMandatory ) :
					bFound = True
					break
			if bFound == False :
				bReject = True
				break
		
		# delete item sets that do not conatin all the mandatory items
		if bReject == True :
			del listItemSetFiltered[nIndexItemSet]
			continue

		# delete all items except the allowed ones
		nIndexItem = 0
		while len(listItemSetFiltered[nIndexItemSet]) > nIndexItem :
			bFound = False
			for strAllowedItem in allowed_items :
				if listItemSetFiltered[nIndexItemSet][nIndexItem].startswith( strAllowedItem ) :
					bFound = True
					break
			if bFound == False :
				del listItemSetFiltered[nIndexItemSet][nIndexItem]
			else :
				nIndexItem = nIndexItem + 1
		
		# next
		nIndexItemSet = nIndexItemSet + 1

	# remove duplicates using sets as order not important here
	if remove_duplicates == True :
		nIndexItemSet1 = 0
		while len(listItemSetFiltered) < nIndexItemSet1 :
			set1 = set( listItemSetFiltered[nIndexItemSet1] )

			nIndexItemSet2 = nIndexItemSet1 + 1
			while len(listItemSetFiltered) < nIndexItemSet2 :
				set2 = set( listItemSetFiltered[nIndexItemSet2] )

				if set1 == set2 :
					# duplicate, so delete itemset 2
					del listItemSetFiltered[nIndexItemSet2]
				else :
					nIndexItemSet2 = nIndexItemSet2 + 1
			
			nIndexItemSet1 = nIndexItemSet1 + 1

	# all done
	return listItemSetFiltered

def execute_association_mining_item_sets( filename_item_sets = None, filename_rules = None, path_rscript = 'Rscript.exe"', path_am_script = 'association_mining_ch.r', working_dir = '.', dict_openie_config = {} ) :

	# vanilla option combines --no-save, --no-restore, --no-site-file, --no-init-file and --no-environ
	listCMD = [
		path_rscript,
		'--vanilla',
		path_am_script,
		filename_item_sets,
		filename_rules,
		]

	dict_openie_config['logger'].info( 'running R script : ' + repr(listCMD))

	p = subprocess.Popen( listCMD, cwd=working_dir, shell=False )
	nErrorCode = p.wait()

	dict_openie_config['logger'].info( 'R code : ' + repr(nErrorCode))
	#if nErrorCode == 1 :
	#	raise Exception('R script returned an error')


def import_association_mining_rules( filename_rules = None, dict_openie_config = {} ) :

	# read all rules into memory
	readHandle = codecs.open( filename_rules, 'r', 'utf-8', errors = 'replace' )
	listLines = readHandle.readlines()
	readHandle.close()

	# parse rules
	# ignore single header row
	# rule_id \t rule \t support \t confidence \t lift \t count
	listRules = []
	nRow = 0
	for strLine in listLines :
		nRow = nRow + 1

		# skip header
		if nRow == 1 :
			continue

		# parse row
		listParts = strLine.strip().split( '\t' )
		if len(listParts) != 6 :
			raise Exception( 'rule row parse failed : ' + repr(strLine) )
		strRule = listParts[1]
		nSupport = float( listParts[2] )
		nConf = float( listParts[3] )
		nLift = float( listParts[4] )
		nCount = int( listParts[5] )

		# parse rule
		matchObj = regexAMRules.match( strRule )
		if matchObj != None :
			if 'ITEMS' in matchObj.groupdict() :
				strItems = matchObj.groupdict()['ITEMS']
			else :
				raise Exception( 'items missing in rule : ' + repr(strRule) )
			if 'INFERENCE' in matchObj.groupdict() :
				strInferItems = matchObj.groupdict()['INFERENCE']
			else :
				raise Exception( 'inference missing in rule : ' + repr(strRule) )
		else :
			raise Exception( 'row parse error : ' + repr(strRule) )

		# remove {} part
		strItems = strItems[1:-1]
		strInferItems = strInferItems[1:-1]

		# parse item lists. note that items might include , in the text so dont use split
		# left side of rule
		listItemSetLeft = []
		if len(strItems) > 0 :
			listComponents = strItems.split('),')
			for strEntry in listComponents :
				if not strEntry.endswith(')') :
					listItemSetLeft.append( strEntry + ')' )
				else :
					listItemSetLeft.append( strEntry )

		# right side of rule
		listItemSetRight = []
		if len(strInferItems) > 0 :
			listComponents = strInferItems.split('),')
			for strEntry in listComponents :
				if not strEntry.endswith(')') :
					listItemSetRight.append( strEntry + ')' )
				else :
					listItemSetRight.append( strEntry )

		tupleRule = ( tuple( listItemSetLeft ), tuple( listItemSetRight ) )

		# add rule
		listRules.append( ( tupleRule, nConf, nSupport, nLift, nCount ) )

	# sort rules (first by conf, then by support, the by lift)
	listRules = sorted( listRules, key=lambda entry: entry[1] * 1000000.0 + entry[2] + 1000.0 + entry[3], reverse=True )

	# all done
	return listRules

def apply_association_mining_rules( list_item_sets = None, list_rules = [], max_inferences = 3, dict_openie_config = {} ) :

	if list_item_sets == None :
		return

	# create a LHS set for each rule. keep strict rule order so first match rule is highest confidence.
	listLHS = []
	listRHS = []
	for ( tupleRule, nConf, nSupport, nLift, nCount ) in list_rules :
		setLHS = set( tupleRule[0] )
		listLHS.append( setLHS )
		setRHS = set( tupleRule[1] )
		listRHS.append( setRHS )

	# loop on each item set
	nIndexItemSet = 0
	while len(list_item_sets) > nIndexItemSet :

		# does this set have a semantic_type() already? if so do not try to infer one
		strAssigned = None
		for strItem in list_item_sets[nIndexItemSet] :
			if strItem.startswith('semantic_type(') == True :
				strAssigned = strItem
				break

		nInference = 0
		if strAssigned != None :
			nInference = 1

		# make a set for items
		setItems = set( list_item_sets[nIndexItemSet] )

		# check left hand side of each rule to see if we can apply it
		for nIndexRule in range(len(listLHS)) :
			if listLHS[nIndexRule].issubset( setItems ) == True :

				# add infered items sets
				for strItem in listRHS[nIndexRule] :
					# check semantic_type(...) does not exist already. if not add it as an inferred_semantic_type(...)
					if not strItem in list_item_sets[nIndexItemSet] :

						strNewItem = 'inferred_' + strItem
						if not strNewItem in list_item_sets[nIndexItemSet] :
							list_item_sets[nIndexItemSet].append( strNewItem )
							nInference = nInference + 1
							if nInference == max_inferences :
								break

			if nInference == max_inferences :
				break

		# next item set
		nIndexItemSet = nIndexItemSet + 1


################################
# main
################################

# only execute if this is the main file
if __name__ == '__main__' :

	#
	# check args
	#
	if len(sys.argv) < 2 :
		print 'Usage: ch_information_extraction_app.py <config file>\n'
		sys.stdout.flush()
		sys.exit(1)
	if not os.path.isfile(sys.argv[1]) :
		print '<config file> ' + sys.argv[1] + ' does not exist\n'
		sys.stdout.flush()
		sys.exit(1)

	# make logger (global to STDOUT)
	LOG_FORMAT = ('%(levelname) -s %(asctime)s %(message)s')
	logger = logging.getLogger( __name__ )
	logging.basicConfig( level=logging.INFO, format=LOG_FORMAT )
	logger.info('logging started')

	# initialize
	readHandle = None
	writeHandle = None

	try :
		# init
		strConfigFile = sys.argv[1]

		# load config
		dictConfig = soton_corenlppy.config_helper.read_config( strConfigFile )

		strInputFile = dictConfig['input_file']
		strInputFormat = dictConfig['input_format']
		strOutputFileItemSet = dictConfig['output_file_item_set']
		strOutputFileProductions = dictConfig['output_file_productions']
		nDocMax = int( dictConfig['max_doc_limit'] )
		setAllowedURI = set( ast.literal_eval( dictConfig['list_allowed_uri'] ) )

		listLangs = dictConfig['language_codes']
		strStanfordTaggerDir = dictConfig['stanford_tagger_dir']
		strStanfordParserDir = dictConfig['stanford_parser_dir']

		strModelPath = dictConfig['model_path']
		strModelJar = dictConfig['model_jar']
		strModelOptions = dictConfig['model_options']

		strLexiconFileExport = dictConfig['export_lexicon_file']
		strLexiconFileImport = dictConfig['import_lexicon_file']
		strSkosLemmaFile = dictConfig['filename_lemma']
		strSkosHyperFile = dictConfig['filename_hypernym']
		strSkosRelatedFile = dictConfig['filename_related']
		strFileFormat = dictConfig['import_file_format']

		strNounTypeRankedFile = dictConfig['noun_types_ranked']
		strNounTypeLexiconFile = dictConfig['noun_types_ch_lexicon']
		strSemanticMappingCHFile = dictConfig['semantic_mapping_ch']

		# setup parser config
		# make sure whitespace does NOT include /\ as we want to use these for patterns later
		# note: don't bother with ' in whitespace as this is handled separately (and removed if not grammatical)
		# \u201a & \u201b == unicode single quote
		# \u201c & \u201d == unicode double quote
		# \u2018 & \u2019 == unicode apostrophe
		# \u2026 == ... unicode chart used by twitter to mark truncated tweet text at end of tweet
		# a null stemmer is provided as we will handle pluruals etc in the regex vocab explicitly (to avoid losing s at end of named entities)
		# for CH data the text is good, so do not treat hythernated tokens as punctuation so we get tokens like 'four-faceted' preserved
		# allow hashtags (stanford parser will POS labelled them NN)

		dictCHConfig = cultural_heritage_parse_lib.get_cultural_heritage_config(
			lang_codes = listLangs,
			logger = logger,
			stanford_tagger_dir = strStanfordTaggerDir,
			stanford_parser_dir = strStanfordParserDir,
			dep_model_path = strModelPath,
			dep_model_jar = strModelJar,
			dep_options = strModelOptions,
			whitespace = u'\'"\u201a\u201b\u201c\u201d\u2018\u2019',
			punctuation = """,;\/:+~&*=!?""",
			allow_hashtags = True,
			sent_token_seps = [ ';', ':', '.', '\n', '\r', '\f', u'\u2026' ],
			apostrophe_handling = 'preserve'
			)

		# check dir exists
		if os.path.exists( strInputFile ) == False :
			raise Exception( 'input file does not exist : ' + strInputFile )

		# Disable stemming and rely on Wordnet morphy() instead as its more reliable
		stemmer = None

		logger.info( '\n#\n# Gravitate - Preparing CH Corpus\n#' )

		logger.info( 'reading corpus : ' + strInputFile )

		# parse JSON from SPARQL
		dictText = {}
		if strInputFormat == 'sparql_json' :

			# read input data
			readHandle = codecs.open( strInputFile, 'r', 'utf-8', errors = 'replace' )
			listLines = readHandle.readlines()
			readHandle.close()

			strJSON = u'\n'.join( listLines )
			dictJSON = json.loads( strJSON, encoding = 'utf-8' )
			if not 'results' in dictJSON :
				raise Exception( 'input JSON does not have a SPARQL results key' )
			if not 'bindings' in dictJSON['results'] :
				raise Exception( 'input JSON does not have a SPARQL bindings key' )
			
			# extract sents and URIs into simple lists
			for dictBinding in dictJSON['results']['bindings'] :
				strURI = dictBinding['artifact']['value']
				strText = dictBinding['text']['value']
				if not strURI in dictText :
					dictText[ strURI ] = []
				dictText[ strURI ].append( strText )

				# apply doc limit
				if (nDocMax != -1) and (len(dictText) >= nDocMax) :
					break

		# parse JSON from SQL
		elif strInputFormat == 'sql_csv' :

			# PostgreSQL export > "image_uri";"text";"source_uri"
			# note: csv.reader does not work for upper UTF-8 characters so might need to manually parse
			readHandle = codecs.open( strInputFile, 'rb', 'utf-8', errors = 'replace' )
			csvReader = csv.reader( readHandle, delimiter=';', quotechar='"')

			bHeader = True
			for listValues in csvReader :
				if bHeader == False :
					strText = listValues[1]
					# crudely remove RT prefix
					if ':' in strText[:10] :
						strText = strText[ strText.index(':') : ]
					strURI = listValues[2]

					if not strURI in dictText :
						dictText[ strURI ] = []
					dictText[ strURI ].append( strText )

					# apply doc limit
					if (nDocMax != -1) and (len(dictText) >= nDocMax) :
						break

				bHeader = False

			readHandle.close()

		# parse JSON from JSON (raw posts)
		elif strInputFormat == 'json' :

			# read input data
			readHandle = codecs.open( strInputFile, 'r', 'utf-8', errors = 'replace' )
			listLines = readHandle.readlines()
			readHandle.close()

			for strLine in listLines :
				if len(strLine.strip()) == 0 :
					continue
				elif strLine.startswith( '#' ) :
					continue
				else :
					#logger.info( repr(strLine.strip()) )
					jsonObj = json.loads( strLine.strip(), encoding = 'utf-8' )

					strUserScreenName = ''
					if 'user' in jsonObj :
						dictUser = jsonObj['user']
						if 'screen_name' in dictUser :
							strUserScreenName = dictUser['screen_name']

					if len(strUserScreenName) > 0 :
						strURI = 'https://twitter.com/' + strUserScreenName + '/status/' + jsonObj['id_str']
					else :
						raise Exception( 'JSON tweet with no screen name : ' + repr(strLine) )

					strText = jsonObj[ 'text' ]

				if not strURI in dictText :
					dictText[ strURI ] = []
				dictText[ strURI ].append( strText )

				# apply doc limit
				if (nDocMax != -1) and (len(dictText) >= nDocMax) :
					break

		else :
			raise Exception( 'unknown input format : ' + strInputFormat )

		logger.info( 'Number of URIs in corpus = ' + str(len(dictText)) )

		# filter URIs
		if len(setAllowedURI) > 0 :
			listKeys = dictText.keys()
			for strURI in listKeys :
				if not strURI in setAllowedURI :
					del dictText[strURI]

		logger.info( 'Number of Allowed URIs in corpus = ' + str(len(dictText)) )

		#
		# prepare dataset dir for corpus sentences so attribie can work on it
		# sent_id \t text \t entity_id
		#
		os.mkdir( 'CH_dataset' )
		writeHandle = codecs.open( 'CH_dataset' + os.sep + 'sentences.txt', 'w', 'utf-8', errors = 'replace' )
		nSentIndex = 0
		dictSentToURIIndex = {}
		for strURI in dictText :
			for strText in dictText[strURI] :
				listLines = strText.strip('\r\n').split('\n')
				for strLine in listLines :

					# avoid embedded tabs and newlines, which will cause errors when reading sentence file back in
					strTextSafe = strLine
					strTextSafe = strTextSafe.replace('\t',' ')

					# tokenize with sent breakdown, as attrib ie expects to be provided with sentences not paragraphs of text.
					listSents = soton_corenlppy.common_parse_lib.unigram_tokenize_text_with_sent_breakdown(
						text = strTextSafe,
						dict_common_config = dictCHConfig )

					for listTokens in listSents :
						strSent = ' '.join( listTokens )
						writeHandle.write( str(nSentIndex) + '\t' + strSent + '\t' + strURI + '\n' )
						dictSentToURIIndex[ nSentIndex ] = strURI
						nSentIndex = nSentIndex + 1

		writeHandle.close()

		#
		# run attrib ie
		#

		listCMD = [
			'python',
			'attrib_ie.py',
			'ch_attrib_ie.ini',
			'generate',
			'attribie-templates.txt',
			'CH_dataset',
			]
		p = subprocess.Popen( listCMD, cwd='.', shell=False )
		logger.info( '\n#\n# Attrib IE - Generate Templates\n#' )
		p.wait()
		if p.returncode != 0 :
			raise Exception( 'template generation failed (attrib ie) : ' + repr(p.returncode) )

		listCMD = [
			'python',
			'attrib_ie.py',
			'ch_attrib_ie.ini',
			'extract',
			'attribie-templates.txt',
			'extractions-attribie.txt',
			'CH_dataset',
			]
		p = subprocess.Popen( listCMD, cwd='.', shell=False )
		logger.info( '\n#\n# Attrib IE - Extract Propositions\n#' )
		p.wait()
		if p.returncode != 0 :
			raise Exception( 'template extract failed (attrib ie) : ' + repr(p.returncode) )

		logger.info( '\n#\n# Gravitate - Semantic Mapping\n#' )

		#
		# Semantic mapping patterns
		#   manual domain-specific patterns
		#
		listSemanticMappings = load_semantic_mapping(
			filename_mapping = strSemanticMappingCHFile,
			dict_openie_config = dictCHConfig
			)
		logger.info( 'SEMANTIC MAPPING manual' )
		logger.info( 'num patterns = ' + repr(len(listSemanticMappings)) )

		#
		# Lexicon creation
		#   manual noun list with domain specific noun type mappings (e.g. part, shape)
		#   CH lexicon with nouns removed if they appear in WordNet (so we keep only the specialist vocabulary)
		#

		# load ranked noun type mappings (will be used as a filter for CH lexicon import and to disambiguate between multiple schema options)
		listNounTypeRanked = read_noun_type_ranked_list(
			filename = strNounTypeRankedFile,
			dict_openie_config = dictCHConfig
			)

		logger.info( 'LEXICON schema list' )
		logger.info( 'num uri = ' + repr(len(listNounTypeRanked)) )

		# load noun type lexicon
		( dictNounTypeLexiconURI, dictNounTypeLexiconPhrase ) = lexicopy.lexicon_lib.import_plain_lexicon(
			filename_lemma = strNounTypeLexiconFile,
			list_column_names = ['schema','phrase_list','hypernym'],
			phrase_delimiter = '|',
			lower_case = True,
			stemmer = stemmer,
			apply_wordnet_morphy = True,
			allowed_schema_list = None,
			dict_lexicon_config = dictCHConfig )

		logger.info( 'LEXICON noun type' )
		logger.info( 'num uri = ' + repr(len(dictNounTypeLexiconURI)) )
		logger.info( 'num phrases = ' + repr(len(dictNounTypeLexiconPhrase)) )

		if strLexiconFileExport != '' :
			# create lexicon from JSON results of BM SPARQL queries (of SKOS vocabulary)
			# use simple stemming to allow plurals to match (e.g. chalices => chalice)
			( dictCHLexiconURI, dictCHLexiconPhrase ) = lexicopy.lexicon_lib.import_skos_lexicon(
				filename_lemma = strSkosLemmaFile,
				filename_hypernym = strSkosHyperFile,
				filename_related = strSkosRelatedFile,
				serialized_format = strFileFormat,
				stemmer = stemmer,
				apply_wordnet_morphy = True,
				allowed_schema_list = listNounTypeRanked,
				dict_lexicon_config = dictCHConfig )

			lexicopy.lexicon_lib.export_lexicon(
				filename_lexicon = strLexiconFileExport,
				dict_uri = dictCHLexiconURI,
				dict_phrase = dictCHLexiconPhrase,
				dict_lexicon_config = dictCHConfig )
			logger.info( 'lexicon exported to ' + strLexiconFileExport )

		else :
			if strLexiconFileImport != '' :

				# load previously prepared lexicon from disk
				( dictCHLexiconURI, dictCHLexiconPhrase ) = lexicopy.lexicon_lib.import_lexicon( filename_lexicon = strLexiconFileImport, dict_lexicon_config = dictCHConfig )
				logger.info( 'lexicon imported from ' + strLexiconFileImport )
			else :
				dictCHLexiconURI = {}
				dictCHLexiconPhrase = {}

		logger.info( 'LEXICON CH' )
		logger.info( 'num uri = ' + repr(len(dictCHLexiconURI)) )
		logger.info( 'num phrases = ' + repr(len(dictCHLexiconPhrase)) )

		# min wordnet count is 0, so ANY mention in WordNet will be removed from the CH lexicon.
		# this avoids 'lotus' for example, with cound 0, being treated as a material (as it is in CH lexicon).
		# this means lexicon will ONLY contain the specialist domain vocab and no any common words.
		lexicopy.lexicon_lib.filter_lexicon_wordnet(
			dict_phrase = dictCHLexiconPhrase,
			count_freq_min = 0,
			dict_lexicon_config = dictCHConfig
			)

		logger.info( 'LEXICON filtered using wordnet' )
		logger.info( 'num uri = ' + repr(len(dictCHLexiconURI)) )
		logger.info( 'num phrases = ' + repr(len(dictCHLexiconPhrase)) )

		# merge it with CH lexicon
		( dictMergedLexiconURI, dictMergedLexiconPhrase ) = lexicopy.lexicon_lib.merge_lexicon(
			list_lexicon = [ ( dictNounTypeLexiconURI, dictNounTypeLexiconPhrase ), ( dictCHLexiconURI, dictCHLexiconPhrase ) ],
			dict_lexicon_config = dictCHConfig
			)

		logger.info( 'LEXICON merged' )
		logger.info( 'num uri = ' + repr(len(dictMergedLexiconURI)) )
		logger.info( 'num phrases = ' + repr(len(dictMergedLexiconPhrase)) )

		#
		# read in annotated propositions extracted from attribie
		#

		strVarFile = 'CH_dataset' + os.sep + 'annotated-extractions-attribie.txt'
		readHandle = codecs.open( strVarFile, 'r', 'utf-8', errors = 'replace' )
		listLines = readHandle.readlines()
		readHandle.close()

		listDocumentPropositionSets = []
		for strLine in listLines :
			if not '\t' in strLine :
				continue
			
			# proposition file
			# ----------------
			# <some sentence text> \n
			# sent_index \t "phrase1" \t "phrase2" ... \t "head1" \t "head2" ... \t conf_float \t {subj,attr,obj}\n
			# sent_index \t "phrase1" \t "phrase2" ... \t "head1" \t "head2" ... \t conf_float \t {subj,attr,obj}\n
			# ...

			listComponents = strLine.strip().split('\t')
			if len(listComponents) < 3 :
				raise Exception( 'bad extraction (parse fail) : ' + strLine )

			strIndexSent = listComponents[0]
			nConf = float(listComponents[-2])
			strPropPattern = listComponents[-1]

			# parse prop pattern into a list (remove wrapping ")
			listPropPattern = strPropPattern[1:-1].split(',')

			listPhraseText = []
			for nIndexProp in range(1,len(listPropPattern)+1) :
				# remove wrapping "'s
				listPhraseText.append( listComponents[nIndexProp][1:-1] )

			listHeadText = []
			for nIndexHead in range(len(listPropPattern)+1,1+len(listPropPattern)*2) :
				# remove wrapping "'s
				listHeadText.append( listComponents[nIndexHead][1:-1] )

			listDocumentPropositionSets.append( ( strIndexSent, listPhraseText, nConf, listPropPattern, listHeadText ) )

		#
		# Semantic mapping to kwowledge base productions (KBP)
		#   create item sets from {arg,rel}arg} variables
		#   semantically map nouns (domain specific noun mapping file) -> subj_type, obj_type
		#   add WordNet subj/obj/rel hypernymns as items -> rel_wn, subj_wn, obj_wn
		#   semantically map rels (domain specific rel mapping file) -> rel_type
		#   association mining (apriori) -> inferred_rel_type
		#     learn rules to infer rel_type based on item sets (confidence 1.0 only)
		#     apply rules to infer rel types
		#   apply domain-specific heuristics to take known rel_type's and make CIDOC-CRM RDF productions
		#

		logger.info( 'SEMANTIC MAPPED EXTRACTIONS (using association mining)' )

		#
		# (1) create compound itemset from extraction set
		#

		# debug
		'''
		for entry in listDocumentPropositionSets :
			logger.info( 'T0 = ' + repr(entry) )
		'''

		listExtractionItemSets = []
		for nSentIndex in dictSentToURIIndex :
			strURI = dictSentToURIIndex[ nSentIndex ]

			for ( strIndexSent, listPhraseText, nConf, listPropPattern, listHeadText ) in listDocumentPropositionSets :
				if strIndexSent == str(nSentIndex) :

					# note last index
					nLastSet = len(listExtractionItemSets)

					# create item sets for this proposition
					add_item_sets_from_extraction(
						list_item_sets = listExtractionItemSets,
						list_extracted_prop = listPhraseText,
						list_head_terms = listHeadText,
						list_prop_pattern = listPropPattern,
						dict_openie_config = dictCHConfig )

					# add artifact URI to all new item sets (useful later when making RDF)
					for nIndexSet in range( nLastSet, len(listExtractionItemSets) ) :
						listExtractionItemSets[nIndexSet].append( 'artifact_uri(' + strURI + ')' )

		# debug
		'''
		for entry in listExtractionItemSets :
			logger.info( 'T1 = ' + repr(entry) )
		'''

		#
		# (2) aggregate patterns to extend compound itemset
		#

		aggregate_phrases_in_item_set( 
			list_item_sets = listExtractionItemSets,
			agg_patterns = [ ('attr',), ('attrbase','attrprep'), ('attrnoobjnosubj',) ],
			agg_var_name = 'attribute',
			dict_openie_config = dictCHConfig
			)

		# debug
		'''
		for entry in listExtractionItemSets :
			logger.info( 'T2 = ' + repr(entry) )
		'''

		#
		# (3) expand compound item sets into single value item sets, and do a lexicon lookup to add type classifications
		#

		expand_compound_items_and_apply_lexicon_schema_mappings(
			list_item_sets = listExtractionItemSets,
			lex_phrase_index = dictMergedLexiconPhrase,
			lex_uri_index = dictMergedLexiconURI,
			schema_ranked_list = listNounTypeRanked,
			stemmer = stemmer,
			dict_openie_config = dictCHConfig
			)

		# debug
		'''
		for entry in listExtractionItemSets :
			logger.info( 'T3 = ' + repr(entry) )
		'''

		#
		# (4) add WordNet troponyms (word with more generalized verb meaning)
		#

		apply_wordnet_mapping_to_item_sets(
			list_item_sets = listExtractionItemSets,
			allowed_types = set(['attribute_head', 'subj_head', 'obj_head']),
			count_freq_threshold = 0.5,
			top_n_lemma = 3,
			dict_openie_config = dictCHConfig
			)

		# debug
		'''
		for entry in listExtractionItemSets :
			logger.info( 'T4 = ' + repr(entry) )
		'''

		#
		# (5) apply manual semantic mapping to generate relation schema types
		#

		apply_semantic_mapping_to_item_sets(
			list_item_sets = listExtractionItemSets,
			list_semantic_mapping = listSemanticMappings,
			dict_openie_config = dictCHConfig
			)

		# debug
		'''
		for entry in listExtractionItemSets :
			logger.info( 'T5 = ' + repr(entry) )
		'''

		# check we have items to process
		if len(listExtractionItemSets) == 0 :
			logger.info( 'Empty item set - cannot create RDF' )
		else :

			#
			# (x) filter and write extraction item sets to disk ready for association mining
			#

			listAssociationMiningItemSets = filter_item_sets(
				list_item_sets = listExtractionItemSets,
				mandatory_items = set([]),
				allowed_items = set(['semantic_type', 'attribute_head', 'subj_head', 'obj_head', 'attribute_wn', 'subj_wn', 'obj_wn']),
				remove_duplicates = True,
				dict_openie_config = dictCHConfig
				)

			# debug
			'''
			for entry in listExtractionItemSets :
				logger.info( 'T6 = ' + repr(entry) )
			'''

			#
			# (x) execute R script to perform association mining
			#

			strFile = strOutputFileItemSet + '.am.txt'
			logger.info( 'item set for am : ' + strFile )
			writeHandle = codecs.open( strFile, 'w', 'utf-8', errors = 'replace' )
			for listItemSet in listAssociationMiningItemSets :
				strLine = '\t'.join( list( listItemSet ) )
				writeHandle.write( strLine + '\n' )
			writeHandle.write( '\n' )
			writeHandle.close()

			execute_association_mining_item_sets(
				filename_item_sets = strFile,
				filename_rules = 'association_mining_rules.txt',
				path_rscript = '/Program Files/R/R-3.4.4/bin/Rscript.exe',
				path_am_script = 'association_mining_ch.r',
				working_dir = '.',
				dict_openie_config = dictCHConfig
				)

			#
			# (x) read association mining rules and apply them to infer new relation schema mappings
			#

			listRules = import_association_mining_rules(
				filename_rules = 'association_mining_rules.txt',
				dict_openie_config = dictCHConfig
				)

			strFile = 'sorted_rules.txt'
			logger.info( 'sorted rules : ' + strFile )
			writeHandle = codecs.open( strFile, 'w', 'utf-8', errors = 'replace' )
			for entry in listRules :
				writeHandle.write(
					repr(entry[0][0]) + ' => ' + repr(entry[0][1])+ ' : ' + repr(entry[1:]) + '\n' )
			writeHandle.write( '\n' )
			writeHandle.close()

			apply_association_mining_rules(
				list_item_sets = listExtractionItemSets,
				list_rules = listRules,
				max_inferences = 3,
				dict_openie_config = dictCHConfig
				)
			#
			# (x) write final item sets as output
			#

			strFile = strOutputFileItemSet
			logger.info( 'item set : ' + strFile )
			writeHandle = codecs.open( strFile, 'w', 'utf-8', errors = 'replace' )

			for listItemSet in listExtractionItemSets :
				strLine = '\t'.join( list( listItemSet ) )
				writeHandle.write( strLine + '\n' )

			writeHandle.write( '\n' )
			writeHandle.close()

			#
			# generate RDF for CH skos:Concept entries that can be read by ReseartchSpace
			#
			logger.info( 'Creating RDF productions for ResearchSpace' )

			logger.info( 'productions: ' + strOutputFileProductions )
			writeHandle = codecs.open( strOutputFileProductions, 'w', 'utf-8', errors = 'replace' )

			strTurtle = cultural_heritage_parse_lib.item_set_to_CIDOC_CRM_RDF(
				item_sets = listExtractionItemSets,
				annotation_namespace = 'http://gravitate.org/id/',
				graph_namespace = 'http://gravitate.org/id/NLP_algorithm/graph',
				include_prefix = True,
				# TODO capture s 's ies es NOT just a simple s at end
				entity_stemmer = nltk.stem.RegexpStemmer('s$', 4),
				dict_ch_config = dictCHConfig )
			if len(strTurtle) > 0 :
				writeHandle.write( strTurtle + '\n' )

			writeHandle.write( '\n' )
			writeHandle.close()

	except :
		logger.exception( 'ch_information_extraction_app main() exception' )
		sys.stderr.flush()
		sys.stdout.flush()

		# close file handler
		if readHandle != None :
			readHandle.close()
		if writeHandle != None :
			writeHandle.close()
		logger.info( 'closed file handles' )

		sys.stdout.flush()
		sys.exit(1)

	# all done
	logger.info('finished')
	sys.stdout.flush()
	sys.exit(0);
