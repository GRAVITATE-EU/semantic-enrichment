# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/////////////////////////////////////////////////////////////////////////
//
// (c) Copyright University of Southampton IT Innovation, 2018
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
//    Created Date :    2018/07/02
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
import test_attrib_ie_regex


'''
Evaluation app for AttribIE
'''

def read_noun_type_ranked_list( filename = None, dict_openie_config = {} ) :

	readHandle = codecs.open( filename, 'r', 'utf-8', errors = 'replace' )
	listLines = readHandle.readlines()
	readHandle.close()

	listRankedNounType = []

	for strLine in listLines :
		if ( len(strLine) > 0 ) and (strLine[0] != '#') :
			listRankedNounType.append( strLine.strip() )
	
	return listRankedNounType


################################
# main
################################

# only execute if this is the main file
if __name__ == '__main__' :

	#
	# check args
	#
	if len(sys.argv) < 5 :
		print 'Usage: test_attrib_ie.py <config file> generate <template file> <dataset> <dataset> ...\n'
		print 'Usage: test_attrib_ie.py <config file> extract <template file> <extract file> <dataset> <dataset> ...\n'
		print 'Usage: test_attrib_ie.py <config file> filter <template file> <filtered template file> <feedback start index> <feedback end index> <dataset> <dataset> ...\n'
		sys.stdout.flush()
		sys.exit(1)

	if not os.path.isfile(sys.argv[1]) :
		print '<config file> ' + sys.argv[1] + ' does not exist\n'
		sys.stdout.flush()
		sys.exit(1)

	if not sys.argv[2] in ['generate','extract','filter'] :
		print '<mode> ' + sys.argv[2] + ' not generate|extract|filter\n'
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
		strMode = sys.argv[2]

		logger.info('Mode: ' + strMode)

		if strMode == 'generate' :
			nDatasetIndex = 4

			strTemplateFile = sys.argv[3]
			logger.info('Template file (output): ' + strTemplateFile)

		elif strMode == 'extract' :
			nDatasetIndex = 5

			strTemplateFile = sys.argv[3]
			logger.info('Template file (input): ' + strTemplateFile)

			strExtractFile = sys.argv[4]
			logger.info('Extract file (output): ' + strExtractFile)
		elif strMode == 'filter' :
			nDatasetIndex = 7

			strTemplateFile = sys.argv[3]
			logger.info('Template file (input): ' + strTemplateFile)

			strFilteredTemplateFile = sys.argv[4]
			logger.info('Filtered template file (output): ' + strFilteredTemplateFile)

			nFeedbackStartIndex = int( sys.argv[5] )
			nFeedbackEndIndex = int( sys.argv[6] )
			logger.info('Feedback index range: ' + repr([nFeedbackStartIndex,nFeedbackEndIndex]))

		listEvalDatasets = []
		for nDataset in range(nDatasetIndex,len(sys.argv)) :
			if not os.path.isdir(sys.argv[nDataset]) :
				raise Exception( '<dataset> ' + sys.argv[nDataset] + ' does not exist' )
			listEvalDatasets.append( sys.argv[nDataset] )

		logger.info('Dataset dir list (input): ' + repr(listEvalDatasets) )

		# load config
		dictConfig = soton_corenlppy.config_helper.read_config( strConfigFile )

		bOutputPOS = ast.literal_eval( dictConfig['output_pos'] )
		bOutputSeed = ast.literal_eval( dictConfig['output_seed'] )
		bOutputPlainExtract = ast.literal_eval( dictConfig['output_plain_extracts'] )
		bOutputEncodedExtract = ast.literal_eval( dictConfig['output_encoded_extracts'] )
		bOutputAnnotatedProp = ast.literal_eval( dictConfig['output_annotated_prop'] )

		nRandomSubsetTraining = int( dictConfig['random_subset_training'] )
		nTargetExtractionTemplates = int( dictConfig['target_extraction_templates'] )
		nProcessMax = int( dictConfig['process_count'] )

		nSentMax = int( dictConfig['max_sent_limit'] )

		listLangs = dictConfig['language_codes']
		strStanfordTaggerDir = dictConfig['stanford_tagger_dir']
		strStanfordParserDir = dictConfig['stanford_parser_dir']

		strModelPath = dictConfig['model_path']
		strModelJar = dictConfig['model_jar']
		strModelOptions = dictConfig['model_options']

		listLexiconFiles = dictConfig['list_lexicon_files']
		strPOSPatternType = dictConfig['pos_pattern_type']
		strStrategyPruneSeedTuples = dictConfig['strategy_seed_tuples']

		nFeedbackPhasesMax = int( dictConfig['relevance_feedback_phases'] )
		nFeedbackPercentagePerPhase = int( dictConfig['relevance_feedback_percentage_per_phase'] )

		if not strStrategyPruneSeedTuples in ['premissive','selective','strict','no_filter'] :
			raise Exception('invalid pruning strategy')

		# setup structure with the right settings for the POS pattern type
		if strPOSPatternType == 'propositional' :
			dict_POS_pattern_settings = {
					'exec_order' : test_attrib_ie_regex.listPropExecutionOrder,
					'pos_patterns' : test_attrib_ie_regex.dictPropPatterns,
					'phrase_patterns' : test_attrib_ie_regex.dictPropVarPhrasePatterns,
					'seed_tuples' : test_attrib_ie_regex.listSeedTuplesProp,
					'prevent_sequence' : test_attrib_ie_regex.listPropPreventSequentialMatchesTriples,
					'seed_var_mapping' : test_attrib_ie_regex.dictPropSeedToTemplateMapping,
					'seed_subsumption' : True, 
					'template_generalization_strategy' : test_attrib_ie_regex.dictGeneralizeStrategyProp,
					'filter_extract_strat' : 'min_semantic_drift_per_target',
					'filter_prop_strat' : 'min_length',
					'prop_stoplist_prefix' : test_attrib_ie_regex.dictPropStoplistPrefixProp,
					'prop_stoplist_suffix' : test_attrib_ie_regex.dictPropStoplistSuffixProp,
					'proposition_pattern' : test_attrib_ie_regex.listPropositionPatternPropSet,
					'displaced_context' : test_attrib_ie_regex.dictDisplacedContextProp,
					'max_semantic_drift' : test_attrib_ie_regex.nMaxSemanticDriftProp,
					'max_end_to_end_semantic_dist' : test_attrib_ie_regex.nMaxEndToEndSemanticDriftProp,
					'semantic_drift_cost' : test_attrib_ie_regex.dictSemanticDriftProp,
					'include_context_in_prop' : True,
					'longest_dep_path' : 128,
					'longest_inter_target_walk' : 5,
					'min_var_connection' : 2,
					'avoid_dep' : test_attrib_ie_regex.setAvoidDepInWalkProp,
					'sent_token_seps' : [ '.', '\n', '\r', '\f', u'\u2026' ],
				}
			strStrategySeedGeneration = 'contiguous_tuple_with_seq_groups'

		elif strPOSPatternType == 'attributional' :
			dict_POS_pattern_settings = {
					'exec_order' : test_attrib_ie_regex.listAttrExecutionOrder,
					'pos_patterns' : test_attrib_ie_regex.dictAttrPatterns,
					'phrase_patterns' : test_attrib_ie_regex.dictAttrVarPhrasePatterns,
					'seed_tuples' : test_attrib_ie_regex.listSeedTuplesAttr,
					'prevent_sequence' : test_attrib_ie_regex.listAttrPreventSequentialMatchesTriples,
					'seed_var_mapping' : test_attrib_ie_regex.dictAttrSeedToTemplateMapping,
					'seed_subsumption' : False, 
					'template_generalization_strategy' : test_attrib_ie_regex.dictGeneralizeStrategyAttr,
					'filter_extract_strat' : 'min_semantic_drift_per_target',
					#'filter_prop_strat' : 'min_length',
					'filter_prop_strat' : 'prop_subsumption',
					'prop_stoplist_prefix' : test_attrib_ie_regex.dictPropStoplistPrefixAttr,
					'prop_stoplist_suffix' : test_attrib_ie_regex.dictPropStoplistSuffixAttr,
					'proposition_pattern' : test_attrib_ie_regex.listPropositionPatternAttrSet,
					'displaced_context' : test_attrib_ie_regex.dictDisplacedContextAttr,
					'max_semantic_drift' : test_attrib_ie_regex.nMaxSemanticDriftAttr,
					'max_end_to_end_semantic_dist' : test_attrib_ie_regex.nMaxEndToEndSemanticDriftAttr,
					'semantic_drift_cost' : test_attrib_ie_regex.dictSemanticDriftAttr,
					'include_context_in_prop' : False,
					'longest_dep_path' : 128,
					'longest_inter_target_walk' : 5,
					'min_var_connection' : 0,
					'avoid_dep' : test_attrib_ie_regex.setAvoidDepInWalkAttr,
					'sent_token_seps' : [ ';', ':', '.', '\n', '\r', '\f', u'\u2026' ],
				}
			strStrategySeedGeneration = 'contiguous_tuple_with_seq_groups'

		else :
			raise Exception( 'unknown pos_pattern_type = ' + repr(strPOSPatternType) )

		# check there is a seed pattern per proposition pattern
		if len( dict_POS_pattern_settings['seed_tuples'] ) != len( dict_POS_pattern_settings['proposition_pattern'] ) :
			raise Exception( 'there should be a 1 to 1 mapping between listSeedTuplesX and listPropositionPatternX' )



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
		# set apostrophe_handling to preserve, so we keep "s'" which gets labelled by Stanford POS tagger as 'POS'
		# dont use any sent tokenizer (t_sent) OR sent token seps, since input data from datasets is manually extracted into sents anyway (and it might get confused with abbreviations like Corp. or monkey.com)

		dictAttribIEConfig = openiepy.openie_lib.get_openie_config(
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
			# sent_token_seps = [ '\n', '\r', '\f', u'\u2026', ';' ],
			#sent_token_seps = [ '\n', '\r', '\f', u'\u2026' ],
			sent_token_seps = dict_POS_pattern_settings['sent_token_seps'],
			t_sent = None,
			apostrophe_handling = 'preserve'
			)

		# add in regex and POS labels for domain-specific label types (e.g. catalogue index containing contain periods, which by default are treated erroneously as sent delimiters)
		# so the common_parse_lib tokenization and POS tagger function picks them up and uses them
		# note: remove NAMESPACE as the alpha_numeric pattern will pick this up (as some CH identifiers are very similar to namespace 123.A67)
		dictAttribIEConfig['token_preservation_regex'] = [ ('regex_url','URI') ]
		for strLabelType in test_attrib_ie_regex.listTagPatternOrder :
			# compile pattern
			rePattern = test_attrib_ie_regex.dictTagPatterns[strLabelType][0]
			strPOSLabel = test_attrib_ie_regex.dictTagPatterns[strLabelType][1]

			# insert new regex POS pattern
			dictAttribIEConfig[strLabelType] = rePattern
			dictAttribIEConfig['token_preservation_regex'].append( ( strLabelType, strPOSLabel ) )

		# Disable stemming and rely on Wordnet morphy() instead as its more reliable
		#stemmer = nltk.stem.RegexpStemmer('s$', min=4)
		stemmer = None

		#
		# Lexicon import
		#   manual noun list with domain specific noun type mappings (e.g. part, shape)
		#   lexicon files specify nouns for filtering purposes later
		#
		logger.info( '\n\nLEXICON\n' )

		listLexicon = []
		listNounTypeRanked = []
		for entry in listLexiconFiles :

			# load ranked noun type mappings (will be used as a filter for lexicon import and to disambiguate between multiple schema options)
			if entry['type'] == 'ranked_list' :
				listNounTypeRanked = read_noun_type_ranked_list(
					filename = entry['file'],
					dict_openie_config = dictAttribIEConfig
					)
				logger.info( 'noun type ranked list = ' + repr(len(listNounTypeRanked)) )

			# load NELL noun phrases
			elif entry['type'] == 'nell' :
				( dictLoadedLexURI, dictLoadedLexPhrase ) = lexicopy.lexicon_lib.import_NELL_lexicon(
					filename_nell = entry['file'],
					stemmer = stemmer,
					lower_case = False,
					apply_wordnet_morphy = True,
					allowed_schema_list = listNounTypeRanked,
					dict_lexicon_config = dictAttribIEConfig )

				listLexicon.append( ( dictLoadedLexURI, dictLoadedLexPhrase ) )
				logger.info( 'loaded num uri = ' + repr(len(dictLoadedLexURI)) )
				logger.info( 'loaded num phrases = ' + repr(len(dictLoadedLexPhrase)) )

			# load plain noun phrases
			elif entry['type'] == 'plain' :
				( dictLoadedLexURI, dictLoadedLexPhrase ) = lexicopy.lexicon_lib.import_plain_lexicon(
					filename_lemma = entry['file'],
					list_column_names = ['schema','phrase_list','hypernym'],
					phrase_delimiter = '|',
					stemmer = stemmer,
					lower_case = False,
					apply_wordnet_morphy = True,
					allowed_schema_list = listNounTypeRanked,
					dict_lexicon_config = dictAttribIEConfig )

				listLexicon.append( ( dictLoadedLexURI, dictLoadedLexPhrase ) )
				logger.info( 'loaded num uri = ' + repr(len(dictLoadedLexURI)) )
				logger.info( 'loaded num phrases = ' + repr(len(dictLoadedLexPhrase)) )

			# load SKOS lexicon
			elif entry['type'] == 'skos_json' :
				( dictLoadedLexURI, dictLoadedLexPhrase ) = lexicopy.lexicon_lib.import_skos_lexicon(
					filename_lemma = entry['lemma'],
					filename_hypernym = entry['hyper'],
					filename_related = entry['related'],
					serialized_format = 'json',
					lower_case = False,
					stemmer = stemmer,
					apply_wordnet_morphy = True,
					allowed_schema_list = listNounTypeRanked,
					dict_lexicon_config = dictAttribIEConfig )

				listLexicon.append( ( dictLoadedLexURI, dictLoadedLexPhrase ) )
				logger.info( 'loaded num uri = ' + repr(len(dictLoadedLexURI)) )
				logger.info( 'loaded num phrases = ' + repr(len(dictLoadedLexPhrase)) )

		# merge lexicon into a single one
		tupleMerged = lexicopy.lexicon_lib.merge_lexicon(
			list_lexicon = listLexicon,
			dict_lexicon_config = dictAttribIEConfig
			)
		if tupleMerged != None :
			( dictLexiconURI, dictLexiconPhrase ) = tupleMerged
		else :
			dictLexiconURI = {}
			dictLexiconPhrase = {}

		logger.info( 'merged num uri = ' + repr(len(dictLexiconURI)) )
		logger.info( 'merged num phrases = ' + repr(len(dictLexiconPhrase)) )

		# min wordnet count is 0, so ANY mention in WordNet will be removed from the CH lexicon.
		# this avoids 'lotus' for example, with count 0, being treated as a material (as it is in CH lexicon).
		# this means lexicon will ONLY contain the specialist domain vocab and no any common words.
		lexicopy.lexicon_lib.filter_lexicon_wordnet(
			dict_phrase = dictLexiconPhrase,
			count_freq_min = 0,
			dict_lexicon_config = dictAttribIEConfig
			)

		logger.info( 'LEXICON filtered using wordnet' )
		logger.info( 'num uri = ' + repr(len(dictLexiconURI)) )
		logger.info( 'num phrases = ' + repr(len(dictLexiconPhrase)) )

		for strDataset in listEvalDatasets :

			logger.info( '\n\nCORPUS : ' + strDataset + '\n' )

			# read in sentence list
			dictText = {}

			# check input file exists
			strInputFile = strDataset + os.sep + 'sentences.txt'
			if os.path.exists( strInputFile ) == False :
				raise Exception( 'input file does not exist : ' + strInputFile )

			# read input data
			readHandle = codecs.open( strInputFile, 'r', 'utf-8', errors = 'replace' )
			listLines = readHandle.readlines()
			readHandle.close()

			# debug
			#listLines = listLines[2890:2895]
			#listLines = listLines[:50]

			nLine = 0
			for strLine in listLines :
				listComponents = strLine.rstrip('\n\r').split( '\t' )
				# clauseIE has format <sentid> <sent>
				# attribIE has format <sentid> <sent> <entityid>
				# oie-benchmark has format <sent>
				# we ignore entity ID but its there for future use should cross-sent co-resolution or discourse level analysis be needed
				if len(listComponents) > 3 :
					raise Exception( 'sentence file parse error : ' + repr(strLine) )

				if len(listComponents) > 1 :

					# unescape out '&AMP ;' and '&AMP;' so its just &
					listComponents[1] = listComponents[1].replace( '&AMP ;', '&' )
					listComponents[1] = listComponents[1].replace( '&AMP;', '&' )

					# replace variants of " used in dataset so its easier to POS and dep parse
					listComponents[1] = listComponents[1].replace( "``", '"' )
					listComponents[1] = listComponents[1].replace( "''", '"' )

					# replace -- with a comma
					listComponents[1] = listComponents[1].replace( "--", ',' )

					# remember sent text
					dictText[ int( listComponents[0] ) ] = listComponents[1]
					nLine = nLine + 1

				else :

					# unescape out '&AMP ;' and '&AMP;' so its just &
					listComponents[0] = listComponents[0].replace( '&AMP ;', '&' )
					listComponents[0] = listComponents[0].replace( '&AMP;', '&' )

					# replace variants of " used in dataset so its easier to POS and dep parse
					listComponents[0] = listComponents[0].replace( "``", '"' )
					listComponents[0] = listComponents[0].replace( "''", '"' )

					# replace -- with a comma
					listComponents[0] = listComponents[0].replace( "--", ',' )

					# remember sent text
					dictText[ nLine ] = listComponents[0]
					nLine = nLine + 1

				# check sent limit
				if (nSentMax != -1) and (nLine >= nSentMax) :
					break

			logger.info( 'Number of sent in corpus = ' + str(len(dictText)) )

			#
			# GENERATE : create a randomly ordered version of the ground truth (so we have a random sample for later relevance feedback work that is consitent across multiple feedback iterations)
			#

			if strMode == 'generate' :

				# load the ground truth data and create a random sample (if we have a ground truth at all)
				strGroundTruth = strDataset + os.sep + 'extractions-all-labelled.txt'
				if os.path.exists( strGroundTruth ) == True :

					listGroundTruth = []

					# read the ground truth data
					readHandle = codecs.open( strGroundTruth, 'r', 'utf-8', errors = 'replace' )
					listLines = readHandle.readlines()
					readHandle.close()

					for strLine in listLines :
						listComponents = strLine.rstrip('\n\r').split( '\t' )
						if len(listComponents) == 1 :
							# ignore sentences
							continue
						elif len(listComponents) > 1 :
							# sent_index, [arg, rel, arg, context], 0|1
							# sent_index, [subj, attr_base, attr_prep, obj], 0|1
							# sent_index, [subj, attr], 0|1
							# sent_index, [subj], 0|1
							nSizeOfExtraction = len(listComponents) - 2
							if nSizeOfExtraction < 1 :
								raise Exception( 'invalid extraction in ground truth : ' + repr(listComponents) )

							# for clauseIE only force it to triples
							if strDataset in ['nyt-clauseIE','reverb-clauseIE','wikipedia-clauseIE'] :
								if nSizeOfExtraction > 3 :
									nSizeOfExtraction = 3

							# remove single quote from both end (not multiple in case string has quotes in it) and make a proposition list
							listProp = []
							for nIndexEntry in range(1,nSizeOfExtraction+1) :
								listProp.append( listComponents[nIndexEntry][1:-1] )

							# add to list (leave numbers as strings)
							listGroundTruth.append( ( listComponents[0], listProp, listComponents[-1] ) )
				
					# randomize the order of ground truth annotations, so feedback sample is a random sample
					# dont shuffle as we want a consistent ground truth list per feedback run (manually shuffle file if this is important)
					random.shuffle( listGroundTruth )

					# serialize random sample of ground truth to file
					strGroundTruthRandom = strDataset + os.sep + 'extractions-all-labelled-randomized.txt'
					writeHandle = codecs.open( strGroundTruthRandom, 'w', 'utf-8', errors = 'replace' )
					for ( nSentIndex, listProp, nScore ) in listGroundTruth :
						writeHandle.write( str(nSentIndex) + '\t' )
						for strPhrase in listProp :
							writeHandle.write( strPhrase + '\t' )
						writeHandle.write( str(nScore) + '\n' )
					writeHandle.close()


			#
			# POS tagging
			#   stanford POS tagger +
			#   Namespace and URI POS patterns + 
			#   CH POS tag patterns for CH-style citations and catalogue identifiers
			#   note: POS patterns are declared in config object - see test_attrib_ie_regex.dictTagPatterns()
			#

			dictSents = {}
			nSentTotal = 0
			for nIndexDoc in sorted( dictText.keys() ) :
				strUTF8Text = dictText[nIndexDoc]

				# note: phrases matching dict_common_config['token_preservation_regex'] regex will be preserved as single tokens
				listTokens = soton_corenlppy.common_parse_lib.unigram_tokenize_text( text = strUTF8Text, dict_common_config = dictAttribIEConfig )
				dictSents[ nIndexDoc ] = [ listTokens ]
				nSentTotal = nSentTotal + 1

			# POS tag document set
			dictTaggedSents = soton_corenlppy.common_parse_lib.pos_tag_tokenset_batch( 
								document_token_set = dictSents,
								lang = 'en',
								dict_common_config = dictAttribIEConfig,
								max_processes = nProcessMax,
								timeout = 300 )

			if bOutputPOS == True :
				# serialize output (POS)
				strPOSFile = strDataset + os.sep + 'pos_labelled_sents.txt'
				logger.info( 'POS tagged sent file: ' + strPOSFile )
				writeHandle = codecs.open( strPOSFile, 'w', 'utf-8', errors = 'replace' )
				for nIndexDoc in sorted( dictTaggedSents.keys() ) :
					writeHandle.write( 'SENT\n' )
					writeHandle.write( str(nIndexDoc) + '\n' )
					writeHandle.write( 'TEXT\n' )
					writeHandle.write( dictText[nIndexDoc] + '\n' )
					writeHandle.write( 'TAGGED SENT\n' )
					for listSent in dictTaggedSents[nIndexDoc] :
						writeHandle.write( soton_corenlppy.common_parse_lib.serialize_tagged_list( list_pos = listSent, dict_common_config = dictAttribIEConfig ) + '\n' )
				writeHandle.close()

			#
			# apply POS patterns to generate seed tuples
			# - propositional seeds -> arg/rel/prep
			# - attributional seeds -> s/a/p/o, s/a/o, s/a/p/<end>, s/a/<end>, <start>/a/<end>, <start>/a/p/<end>
			#

			# create a set of sent trees
			logger.info( '\n\nSENT TREES\n' )
			dictSentTrees = {}
			dictSentTreesPOSPatterns = {}

			for nIndexDoc in dictTaggedSents :
				dictSentTrees[nIndexDoc] = []
				for listSentTagged in dictTaggedSents[nIndexDoc] :
					listSentTrees = soton_corenlppy.common_parse_lib.create_sent_trees( list_pos = listSentTagged, dict_common_config = dictAttribIEConfig )

					#listSentTrees = listSentTrees[7:8]

					# logger.info( '\n\nSENT == ' + repr(listSentTrees) )

					'''
					# use CH domain specific POS-patterns to label sequences of POS tags in sent trees
					listSentMatchesTotal = [[]] * len(listSentTrees)
					for dictPatterns in [
						test_attrib_ie_regex.dictCHIdentifierPatterns,
						test_attrib_ie_regex.dictCHAttributePatterns ] :

						listSentMatches = soton_corenlppy.common_parse_lib.match_linguistic_patterns(
							list_sent_trees = listSentTrees,
							pattern_dict = dictPatterns,
							dict_common_config = dictAttribIEConfig )

						for nIndexSent in range(len(listSentMatchesTotal)) :

							if len( listSentMatches[nIndexSent] ) > 0 :
								#logger.info( 'MATCHES = ' + repr( listSentMatches ) )

								# note: copy list as we will extend it otherwise we change the original list
								listExisting = copy.deepcopy( listSentMatchesTotal[nIndexSent] )
								listNew = listSentMatches[nIndexSent]
								listExisting.extend( listNew )

								listSentMatchesTotal[nIndexSent] = listExisting

					# annotate sent trees with matches for entities, attributes and relationships (this will create n-gram phrases for matched CH concepts)
					listSentTrees = soton_corenlppy.common_parse_lib.annotate_sent_with_pattern_matches(
						list_sent_trees = listSentTrees,
						list_sent_matches = listSentMatchesTotal,
						dict_common_config = dictAttribIEConfig )
					'''

					dictSentTrees[nIndexDoc].extend( listSentTrees )

			# annotate sents with the POS patterns (arg, rel, prep, numeric)
			for nIndexDoc in dictSentTrees :
				listSentTreeAnnotated = openiepy.comp_sem_lib.annotate_using_pos_patterns(
					list_sent_trees = dictSentTrees[nIndexDoc],
					list_phrase_sequence_patterns_exec_order = dict_POS_pattern_settings['exec_order'],
					dict_phrase_sequence_patterns = dict_POS_pattern_settings['pos_patterns'],
					dict_openie_config = dictAttribIEConfig )
				dictSentTreesPOSPatterns[nIndexDoc] = listSentTreeAnnotated

			#
			# Dependency graphs
			#

			# get dependency parser
			logger.info( '\n\nDEP PARSE\n' )
			dep_parser = openiepy.comp_sem_lib.get_dependency_parser( dict_openie_config = dictAttribIEConfig )

			# dependancy parse tagged sents
			dictDepGraphs = openiepy.comp_sem_lib.parse_sent_trees_batch(
				dict_doc_sent_trees = dictSentTrees,
				dep_parser = dep_parser,
				dict_custom_pos_mappings = test_attrib_ie_regex.dictTagDependancyParseMapping,
				max_processes = nProcessMax,
				dict_openie_config = dictAttribIEConfig )

			logger.info( 'dep graphs = ' + str(len(dictDepGraphs)) )

			#
			# GENERATE : seed tuples, open extraction templates, save templates to file
			# note: we generate seeds, templates and extractions *per pattern* to avoid longer patterns (subj, attr, prep, obj} being filtered in preference to shorter ones {subj, attr, obj} later
			#

			if strMode == 'generate' :

				# extract seed_tuples from annotated sents
				logger.info( '\n\nSEED TUPLES\n' )
				dictSeedTuplesPerPattern = {}
				dictVarCandidatesPerPattern = {}

				# generate seeds for each set of patterns (so we can generate separate templates for each pattern)
				for nIndexPattern in range(len(dict_POS_pattern_settings['seed_tuples'])) :
					#logger.info( 'pattern : ' + str(nIndexPattern) )

					tupleSeedPattern = dict_POS_pattern_settings['seed_tuples'][nIndexPattern]
					listSeqSeedPattern = [ tupleSeedPattern ]

					listSeedTuplesTotal = []
					dictVarCandidatesTotal = {}

					for nIndexDoc in dictSentTrees :

						#logger.info('S0 = ' + repr(nIndexDoc) )

						'''
						listSentExtractions = openiepy.comp_sem_lib.extract_annotations_from_sents(
							list_sent_trees = dictSentTreesPOSPatterns[nIndexDoc],
							set_annotations = set( dict_POS_pattern_settings['exec_order'] ),
							dict_openie_config = dictAttribIEConfig )

						listSeedTuples = openiepy.comp_sem_lib.get_seed_tuples_from_extractions(
							list_sent_extractions = listSentExtractions,
							list_sequences = dict_POS_pattern_settings['seed_tuples'],
							prevent_sequential_instances = dict_POS_pattern_settings['prevent_sequence'],
							dict_openie_config = dictAttribIEConfig )
						'''

						if len(dictLexiconPhrase) > 0 :
							tupleLexiconFilter = ( dictLexiconURI, dictLexiconPhrase )
						else :
							tupleLexiconFilter = None

						( listSeedTuples, dictVarCandidates ) = openiepy.comp_sem_lib.generate_seed_tuples(
							list_sent_trees = dictSentTreesPOSPatterns[nIndexDoc],
							generation_strategy = strStrategySeedGeneration,
							lexicon_filter = tupleLexiconFilter,
							set_annotations = set( dict_POS_pattern_settings['exec_order'] ),
							dict_annotation_phrase_patterns = dict_POS_pattern_settings['phrase_patterns'],
							list_sequences = listSeqSeedPattern,
							prevent_sequential_instances = dict_POS_pattern_settings['prevent_sequence'],
							dict_openie_config = dictAttribIEConfig )

						# merge sent results into total
						listSeedTuplesTotal.extend( listSeedTuples )

						for strVarType in dictVarCandidates :
							if not strVarType in dictVarCandidatesTotal :
								dictVarCandidatesTotal[strVarType] = []
							for tupleVarPhrase in dictVarCandidates[strVarType] :
								if not tupleVarPhrase in dictVarCandidatesTotal[strVarType] :
									dictVarCandidatesTotal[strVarType].append( tupleVarPhrase )

					# make a set to remove any duplicates
					setSeedTuplesTotal = set( listSeedTuplesTotal )

					# filter seed_tuple arguments using lexicon (to ensure they are high quality matches that appear)
					# allow any relation type as the majority are not present in lexicon anyway (e.g. has)
					# strategy A (permissive): make sure at least 1 arg or rel is in the lexicon
					# strategy B (selective): make sure at least 2 arg or rel is in the lexicon
					# strategy C (strict): make sure at least all arg or rel is in the lexicon
					if len(dictLexiconURI) > 0 :
						listSeedTuplesTotal = list( setSeedTuplesTotal )
						nIndex = 0
						while nIndex < len(listSeedTuplesTotal) :
							nVarsOK = 0
							nVarsChecked = 0

							for nIndexVar in range(len(listSeedTuplesTotal[nIndex])) :
								tupleSeed = listSeedTuplesTotal[nIndex][nIndexVar]
								strVarType = tupleSeed[0]
								listPhrase = list( tupleSeed[1:] )

								# only filter noun phrase types (i.e. arg, subject, object)
								if strVarType in ['ARGUMENT','SUBJECT','OBJECT'] :

									nVarsChecked = nVarsChecked + 1

									# stem if needed
									if stemmer != None :
										for nIndex2 in range(len(listPhrase)) :
											listPhrase[nIndex2] = stemmer.stem( listPhrase[nIndex2].lower() )

									# get all possible lexicon matches
									listLexiconMatch = lexicopy.lexicon_lib.phrase_lookup(
										phrase_tokens = listPhrase,
										head_token = None,
										lex_phrase_index = dictLexiconPhrase,
										lex_uri_index = dictLexiconURI,
										max_gram = 5,
										stemmer = stemmer,
										apply_wordnet_morphy = True,
										hyphen_variant = True,
										dict_lexicon_config = dictAttribIEConfig )

									# any match is OK
									if len(listLexiconMatch) > 0 :
										nVarsOK = nVarsOK + 1
							
							# prune seed tuples to ensure only good ones remain prior to generating open templates
							bFailed = False
							if strStrategyPruneSeedTuples == 'premissive' :
								# strategy A (permissive): make sure at least 1 arg or rel is in the lexicon
								if nVarsOK == 0 :
									bFailed = True
							elif strStrategyPruneSeedTuples == 'selective' :
								# strategy B (selective): make sure at least 2 vars match in set, unless only one then allow 1
								if nVarsOK < 2 :
									bFailed = True
								if (nVarsChecked == 1) and (nVarsOK != 1) :
									bFailed = True
							elif strStrategyPruneSeedTuples == 'strict' :
								# strategy C (strict): make sure at least all arg or rel is in the lexicon
								if nVarsOK != nVarsChecked :
									bFailed = True
							elif strStrategyPruneSeedTuples == 'no_filter' :
								# do nothing
								pass

							# delete seed tuples that fail lexicon lookup
							if bFailed == True :
								del listSeedTuplesTotal[nIndex]
							else :
								nIndex = nIndex + 1
						setSeedTuplesTotal = set( listSeedTuplesTotal )

					dictSeedTuplesPerPattern[nIndexPattern] = setSeedTuplesTotal
					dictVarCandidatesPerPattern[nIndexPattern] = dictVarCandidatesTotal

					# write seeds to file
					if bOutputSeed == True :
						strSeedFile = strDataset + os.sep + str(nIndexPattern) + '_' + 'seed_tuples.txt'
						writeHandle = codecs.open( strSeedFile, 'w', 'utf-8', errors = 'replace' )
						writeHandle.write( 'SEED TUPLES\n' )
						for tupleSeed in setSeedTuplesTotal :
							writeHandle.write( repr(tupleSeed) + '\n' )

						writeHandle.write( '\nVAR CANDIDATES\n' )
						for strVarType in dictVarCandidatesTotal :
							writeHandle.write( repr( strVarType ) + '\n' )
							for tuplePhrase in dictVarCandidatesTotal[strVarType] :
								writeHandle.write( '\t' + repr( tuplePhrase ) + '\n' )

						writeHandle.close()

				#
				# Learn open extraction templates
				#   use a random set of corpus sentences for training (e.g. 500 or 1000)
				#   use all seed tuples
				#   dep graph walk uses a set of universal dependencies
				#     allowing BOTH {arg,rel,arg} and {arg,prep,arg}
				#     capture negation and genuine/false patterns
				#     allow long graph walks (up to 15 steps) to get the long tail context
				#   aggresively normalize patterns (merge them into more general patterns)
				#     keep topN (e.g. 1000) based on frequency of occurance
				#   note: use a process farm to max CPU as this is a slow process
				#

				# create extraction templates based on a random subset of the whole data as its taking 1.5 minutes per artifact description on average
				# e.g. 500 artifacts takes 0.5 day of processing with a 15 deep graph walk
				listDocURI = dictDepGraphs.keys()
				random.shuffle( listDocURI )
				if nRandomSubsetTraining < len(listDocURI) :
					listDocURI = listDocURI[:nRandomSubsetTraining]

				dictRandomSubsetGraphs = {}
				for strDocURI in listDocURI :
					dictRandomSubsetGraphs[strDocURI] = dictDepGraphs[strDocURI]

				# generate templates for each set of patterns (so we can generate separate templates for each pattern)
				for nIndexPattern in range(len(dict_POS_pattern_settings['seed_tuples'])) :
					logger.info( 'pattern : ' + str(nIndexPattern) )
					setSeedTuplesTotal = dictSeedTuplesPerPattern[nIndexPattern]
					dictVarCandidatesTotal = dictVarCandidatesPerPattern[nIndexPattern]

					# extract from corpus all sents where a seed_tuple exists somewhere in sent structure, but without any constraint on lexical position -> training_sents
					listOpenExtractionPatternsTotal= openiepy.comp_sem_lib.generate_open_extraction_templates_batch(
						seed_tuples = setSeedTuplesTotal,
						var_candidates = dictVarCandidatesTotal,
						dict_document_sent_graphs = dictRandomSubsetGraphs,
						dict_seed_to_template_mappings = dict_POS_pattern_settings['seed_var_mapping'],
						dict_context_dep_types = test_attrib_ie_regex.dictContextualDepTypes,
						max_processes = nProcessMax,
						longest_dep_path = dict_POS_pattern_settings['longest_dep_path'],
						longest_inter_target_walk = dict_POS_pattern_settings['longest_inter_target_walk'],
						max_seed_variants = 128,
						allow_seed_subsumption = dict_POS_pattern_settings['seed_subsumption'],
						avoid_dep_set = dict_POS_pattern_settings['avoid_dep'],
						dict_openie_config = dictAttribIEConfig )

					listOpenExtractionPatternsBeforeNormalization = copy.deepcopy( listOpenExtractionPatternsTotal )
					logger.info( 'patterns before normalization = ' + str(len(listOpenExtractionPatternsBeforeNormalization)) )

					# debug
					'''
					logger.info( 'SPECIFIC PATTERNS' )
					for strPattern in listOpenExtractionPatternsTotal :
						logger.info( repr(strPattern) )
					'''

					# aggresively normalize patterns. keep topN based on freq of occurance.
					listOpenExtractionPatternsTotal = openiepy.comp_sem_lib.normalize_open_extraction_templates(
						list_patterns = listOpenExtractionPatternsTotal,
						topN = nTargetExtractionTemplates,
						dict_generalize_strategy = dict_POS_pattern_settings['template_generalization_strategy'],
						dict_openie_config = dictAttribIEConfig )
					logger.info( 'patterns after normalization = ' + str(len(listOpenExtractionPatternsTotal)) )

					# debug
					'''
					logger.info( 'NORMALIZED PATTERNS' )
					for strPattern in listOpenExtractionPatternsTotal :
						logger.info( repr(strPattern) )
					'''

					# write open pattern templates to disk
					strTemplateFileNew = strDataset + os.sep + strTemplateFile + '_' + str(nIndexPattern) + '.txt'
					logger.info( 'writing open extraction templates to file ' + strTemplateFileNew )
					writeHandle = codecs.open( strTemplateFileNew, 'w', 'utf-8', errors = 'replace' )
					for strPattern in listOpenExtractionPatternsTotal :
						writeHandle.write( strPattern + '\n' )
					writeHandle.close()

			#
			# FILTER : load ground truth
			#

			listGroundTruth = None

			if strMode == 'filter' :

				logger.info( '\n\nLOAD GROUND TRUTH\n' )

				# load the ground truth data for use in relevance feedback (optional)
				listGroundTruth = None
				strGroundTruth = strDataset + os.sep + 'extractions-all-labelled-randomized.txt'
				if os.path.exists( strGroundTruth ) == True :

					listGroundTruth = []

					# read the ground truth data
					readHandle = codecs.open( strGroundTruth, 'r', 'utf-8', errors = 'replace' )
					listLines = readHandle.readlines()
					readHandle.close()

					for strLine in listLines :
						listComponents = strLine.rstrip('\n\r').split( '\t' )
						if len(listComponents) == 1 :
							# ignore sentences
							continue
						elif len(listComponents) > 1 :
							# sent_index, [arg, rel, arg, context], 0|1
							# sent_index, [subj, attr_base, attr_prep, obj], 0|1
							# sent_index, [subj, attr], 0|1
							# sent_index, [subj], 0|1
							nSizeOfExtraction = len(listComponents) - 2
							if nSizeOfExtraction < 1 :
								raise Exception( 'invalid extraction in ground truth : ' + repr(listComponents) )

							# for clauseIE only force it to triples
							if strDataset in ['nyt-clauseIE','reverb-clauseIE','wikipedia-clauseIE'] :
								if nSizeOfExtraction > 3 :
									nSizeOfExtraction = 3

							# remove single quote from both end (not multiple in case string has quotes in it) and make a proposition list
							listProp = []
							for nIndexEntry in range(1,nSizeOfExtraction+1) :
								listProp.append( listComponents[nIndexEntry][1:-1] )

							# add to list (leave numbers as strings)
							listGroundTruth.append( ( listComponents[0], listProp, listComponents[-1] ) )
				
					# randomize the order of ground truth annotations, so feedback sample is a random sample
					# dont shuffle as we want a consistent ground truth list per feedback run (manually shuffle file if this is important)
					#random.shuffle( listGroundTruth )
				else :
					raise Exception( 'missing ground truth file : ' + strGroundTruth )

			#
			# EXTRACT & FILTER : load templates from file, execute templates to generate extractions
			#

			if (strMode == 'extract') or (strMode == 'filter') :

				logger.info( '\n\nEXTRACT VARS\n' )

				dictExtractedVarsUnfilteredPerPattern = {}
				dictExtractedVarsPerPattern = {}
				dictExtractedVarsConfPerPattern = {}
				dictParsedExtractionPatternsPerPattern = {}

				# execute templates for each set of patterns (so we can generate separate extractions for each pattern)
				for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
					logger.info( 'pattern : ' + str(nIndexPattern) )

					listPropPattern = dict_POS_pattern_settings['proposition_pattern'][nIndexPattern][0]
					nTargetIndex = dict_POS_pattern_settings['proposition_pattern'][nIndexPattern][1]
					strTargetVarType = dict_POS_pattern_settings['proposition_pattern'][nIndexPattern][2]

					# read templates from file
					strFileToOpen = strDataset + os.sep + strTemplateFile + '_' + str(nIndexPattern) + '.txt'
					if not os.path.isfile(strFileToOpen) :
						raise Exception( '<template file> ' + strFileToOpen + ' does not exist' )
					logger.info( 'reading open extraction templates to file ' + strFileToOpen )
					readHandle = codecs.open( strFileToOpen, 'r', 'utf-8', errors = 'replace' )
					listLines = readHandle.readlines()
					readHandle.close()

					listOpenExtractionPatternsTotal = []
					for strLine in listLines :
						strPattern = strLine.rstrip('\n\r')
						listOpenExtractionPatternsTotal.append( strPattern )

					# parse open pattern templates 
					listParsedExtractionPatterns = []
					for strPattern in listOpenExtractionPatternsTotal :
						listParsedExtractionPatterns.append(
							openiepy.comp_sem_lib.parse_extraction_pattern(
								str_pattern = strPattern,
								dict_openie_config = dictAttribIEConfig )
							)

					#
					# Execute open extraction templates
					#    report arg, rel, arg
					#    report dep connections between arg/rel variables so we can later use subj/obj etc to make good semantic mappings
					#

					# execute open pattern templates on the test corpus
					dictExtractedVarsUnfiltered = openiepy.comp_sem_lib.match_extraction_patterns_batch(
						dict_document_sent_graphs = dictDepGraphs,
						list_extraction_patterns = listParsedExtractionPatterns,
						dict_collapse_dep_types = test_attrib_ie_regex.dictCollapseDepTypes,
						max_processes = nProcessMax,
						dict_openie_config = dictAttribIEConfig )

					logger.info( 'documents = ' + str(len(dictExtractedVarsUnfiltered)) )

					# filter extractions to avoid variable subsumption
					dictExtractedVars = {}
					dictExtractedVarsConf = {}
					for nIndexDoc in dictDepGraphs :
						if not nIndexDoc in dictExtractedVars :
							dictExtractedVars[nIndexDoc] = []
							dictExtractedVarsConf[nIndexDoc] = []

						#logger.info( '****** T0 = ' + repr(nIndexDoc) )
						#logger.info( repr( dictText[nIndexDoc] ) )
						#logger.info( '' )
						#logger.info( '' )

						for nSentIndex in range(len(dictExtractedVarsUnfiltered[nIndexDoc])) :
							listMatches = dictExtractedVarsUnfiltered[nIndexDoc][nSentIndex]

							( listMatchesFiltered, listConf ) = openiepy.comp_sem_lib.filter_extractions(
								dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
								list_extractions = listMatches,
								filter_strategy = dict_POS_pattern_settings['filter_extract_strat'],
								use_context = False,
								max_context = 100,
								min_var_connection = dict_POS_pattern_settings['min_var_connection'],
								max_semantic_drift = dict_POS_pattern_settings['max_semantic_drift'],
								target_var_type = strTargetVarType,
								dict_sem_drift = dict_POS_pattern_settings['semantic_drift_cost'],
								dict_openie_config = dictAttribIEConfig )

							dictExtractedVars[nIndexDoc].append( listMatchesFiltered )
							dictExtractedVarsConf[nIndexDoc].append( listConf )

						#if nIndexDoc == 6 :
						#	sys.exit()

					dictExtractedVarsUnfilteredPerPattern[nIndexPattern] = dictExtractedVarsUnfiltered
					dictExtractedVarsPerPattern[nIndexPattern] = dictExtractedVars
					dictExtractedVarsConfPerPattern[nIndexPattern] = dictExtractedVarsConf
					dictParsedExtractionPatternsPerPattern[nIndexPattern] = listParsedExtractionPatterns

					logger.info( 'documents (filtered)' )

			#
			# EXTRACT : save extraction variables to disk
			#

			if strMode == 'extract' :

				logger.info( '\n\nSAVE VARS\n' )

				# save extractions for each set of patterns
				for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
					logger.info( 'pattern : ' + str(nIndexPattern) )

					dictExtractedVarsUnfiltered = dictExtractedVarsUnfilteredPerPattern[nIndexPattern]
					dictExtractedVars = dictExtractedVarsPerPattern[nIndexPattern]
					dictExtractedVarsConf = dictExtractedVarsConfPerPattern[nIndexPattern]

					if bOutputPlainExtract == True :

						# serialize output (extracted vars)
						strVarFile = strDataset + os.sep + 'var-' + strExtractFile + '_' + str(nIndexPattern) + '.txt'
						logger.info( 'Extracted variables file: ' + strVarFile )
						writeHandle = codecs.open( strVarFile, 'w', 'utf-8', errors = 'replace' )

						#writeHandle.write( '\nPre-NORMALIZED PATTERNS\n' )
						#for strPattern in listOpenExtractionPatternsBeforeNormalization :
						#	writeHandle.write( repr( strPattern ) + '\n' )

						writeHandle.write( '\nNORMALIZED PATTERNS\n' )
						for strPattern in listOpenExtractionPatternsTotal :
							writeHandle.write( repr( strPattern ) + '\n' )

						writeHandle.write( '\nALL EXTRACTS (unfiltered)\n' )
						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							for nSentIndex in range(len(dictExtractedVarsUnfiltered[nIndexDoc])) :

								treeSent = dictSentTreesPOSPatterns[nIndexDoc][nSentIndex]
								writeHandle.write( u' '.join( treeSent.leaves() ) + '\n' )

								for nMatchIndex in range(len(dictExtractedVarsUnfiltered[nIndexDoc][nSentIndex])) :
									strPrettyText = openiepy.comp_sem_lib.pretty_print_extraction(
										list_extracted_vars = dictExtractedVarsUnfiltered[nIndexDoc][nSentIndex][nMatchIndex],
										dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
										set_var_types = set( test_attrib_ie_regex.setGraphDepTypes ),
										style = 'highlighted_vars',
										dict_openie_config = dictAttribIEConfig )

									writeHandle.write( '\t' + strPrettyText + '\n' )

						writeHandle.write( '\nALL EXTRACTS (filtered)\n' )
						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							for nSentIndex in range(len(dictExtractedVars[nIndexDoc])) :

								treeSent = dictSentTreesPOSPatterns[nIndexDoc][nSentIndex]
								writeHandle.write( u' '.join( treeSent.leaves() ) + '\n' )

								for nMatchIndex in range(len(dictExtractedVars[nIndexDoc][nSentIndex])) :
									strPrettyText = openiepy.comp_sem_lib.pretty_print_extraction(
										list_extracted_vars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex],
										dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
										set_var_types = set( test_attrib_ie_regex.setGraphDepTypes ),
										style = 'highlighted_vars',
										dict_openie_config = dictAttribIEConfig )

									writeHandle.write( '\t' + strPrettyText + '\n' )

						# extracted in human form
						writeHandle.write( '\nALL EXTRACTS (filtered, human formatted variables)\n' )
						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							writeHandle.write( dictText[nIndexDoc] + '\n' )

							for nSentIndex in range(len(dictExtractedVars[nIndexDoc])) :
								for nMatchIndex in range(len(dictExtractedVars[nIndexDoc][nSentIndex])) :

									writeHandle.write( '\textract ' + str(nMatchIndex) + '\n' )

									# get extraction vars
									# listExtractedVars = [ ( var_type, var_name, graph_address, collapsed_graph_addresses[], { dep : [ var_name, ... ] }, pattern_index ), ... ]
									listExtractedVars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex]

									# encode extraction
									strEncoded = openiepy.comp_sem_lib.encode_extraction(
										list_extracted_vars = listExtractedVars,
										dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
										set_var_types = set( test_attrib_ie_regex.setGraphDepTypes ),
										dict_openie_config = dictAttribIEConfig )

									# parse extraction into the form needed by map_encoded_extraction_to_lexicon()
									# listExtractedVarsParsed = [ ( var_name, var_head, var_phrase, { dep_path : [ var,var... ], ... }, addr, pattern_index, var_phrase_human ), ... ]
									listExtractedVarsParsed = openiepy.comp_sem_lib.parse_encoded_extraction(
										encoded_str = strEncoded,
										dict_openie_config = dictAttribIEConfig )

									# output extracted variables in human format
									for ( strVarName, strVarHead, strVarPhrase, dictConnections, nAddr, nPatternIndex, strVarHuman ) in listExtractedVarsParsed :
										writeHandle.write( '\t\t{' + strVarName + '} == ' + strVarHuman + '\n' )

						writeHandle.write( '\nPER URI RESULTS\n' )
						writeHandle.write( '---------------\n' )

						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							listTaggedSents = dictTaggedSents[nIndexDoc]
							listSentGraphs = dictDepGraphs[nIndexDoc]
							listSentVars = dictExtractedVars[nIndexDoc]

							writeHandle.write( '\nURI\n' )
							writeHandle.write( str(nIndexDoc) + '\n' )

							writeHandle.write( '\nTEXT\n' )
							writeHandle.write( dictText[nIndexDoc] + '\n' )

							writeHandle.write( '\SENTS and EXTRACTS\n' )
							for nSentIndex in range(len(dictExtractedVars[nIndexDoc])) :
								treeSent = dictSentTreesPOSPatterns[nIndexDoc][nSentIndex]
								writeHandle.write( soton_corenlppy.common_parse_lib.serialize_tagged_tree( treeSent, dict_common_config = dictAttribIEConfig ) + '\n' )
								writeHandle.write( unicode( treeSent ) + '\n' )

								for nMatchIndex in range(len(dictExtractedVars[nIndexDoc][nSentIndex])) :

									strPrettyText = openiepy.comp_sem_lib.pretty_print_extraction(
										list_extracted_vars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex],
										dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
										set_var_types = set( test_attrib_ie_regex.setGraphDepTypes ),
										style = 'highlighted_vars',
										dict_openie_config = dictAttribIEConfig )

									writeHandle.write( '>> ' + strPrettyText + '\n' )

									listVars = openiepy.comp_sem_lib.get_extraction_vars(
										list_extracted_vars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex],
										dict_openie_config = dictAttribIEConfig )
									for ( strVar, strType ) in listVars :
										tuplePrettyVar = openiepy.comp_sem_lib.pretty_print_extraction_var(
											list_extracted_vars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex],
											dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
											var_name = strVar,
											dict_openie_config = dictAttribIEConfig )
										if tuplePrettyVar[0] != None :
											writeHandle.write( '\t' + strVar + ' = ' + tuplePrettyVar[0] + ' [' + repr(tuplePrettyVar[1]) + ']' )
										if tuplePrettyVar[2] == True :
											writeHandle.write( ' negated' )
										writeHandle.write( '\n' )

							writeHandle.write( '\nTAG\n' )
							for listSent in dictTaggedSents[nIndexDoc] :
								writeHandle.write( soton_corenlppy.common_parse_lib.serialize_tagged_list( list_pos = listSent, dict_common_config = dictAttribIEConfig ) + '\n' )

							writeHandle.write( '\nGRAPH\n' )
							for depObj in dictDepGraphs[nIndexDoc] :
								writeHandle.write( depObj.to_dot() + '\n' )

						writeHandle.close()

					if bOutputEncodedExtract == True :

						# serialize output (extracted vars)
						strVarFile = strDataset + os.sep + 'encoded-var-' + strExtractFile + '_' + str(nIndexPattern) + '.txt'
						logger.info( 'Extracted variables file: ' + strVarFile )
						writeHandle = codecs.open( strVarFile, 'w', 'utf-8', errors = 'replace' )

						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							listTaggedSents = dictTaggedSents[nIndexDoc]
							listSentGraphs = dictDepGraphs[nIndexDoc]
							listSentVars = dictExtractedVars[nIndexDoc]

							for nSentIndex in range(len(dictExtractedVars[nIndexDoc])) :
								treeSent = dictSentTreesPOSPatterns[nIndexDoc][nSentIndex]

								for nMatchIndex in range(len(dictExtractedVars[nIndexDoc][nSentIndex])) :

									# get extraction vars
									# listExtractedVars = [ ( var_type, var_name, graph_address, collapsed_graph_addresses[], (negated, genuine), { dep : [ var_name, ... ] } ), ... ]
									listExtractedVars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex]

									# encode extraction
									strEncoded = openiepy.comp_sem_lib.encode_extraction(
										list_extracted_vars = listExtractedVars,
										dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
										set_var_types = set( test_attrib_ie_regex.setGraphDepTypes ),
										dict_openie_config = dictAttribIEConfig )

									writeHandle.write( str(nIndexDoc) + '\t' + strEncoded + '\n' )

						writeHandle.close()

			#
			# EXTRACT & FILTER : generate save extracted propositions
			#

			if (strMode == 'extract') or (strMode == 'filter') :

				#
				# generate output {arg, rel, arg} in format suitable for evaluation
				#

				logger.info( '\n\nGENERATE PROPOSITIONS\n' )

				dictDocumentPropositionSetsPerPattern = {}
				for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
					dictDocumentPropositionSetsPerPattern[nIndexPattern] = []

				listDocumentPropositionSetsAggregated = []

				# loop on each document
				listDocumentPropositionSets = []
				for nIndexDoc in sorted( dictDepGraphs.keys() ) :
					for nSentIndex in range(len(dictExtractedVars[nIndexDoc])) :

						listPropSetAggregate = []
						listPropSetConfAggregate = []

						# generate propositions for this document from extraction data for each set of patterns
						for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
							#logger.info( 'pattern : ' + str(nIndexPattern) )

							dictExtractedVarsUnfiltered = dictExtractedVarsUnfilteredPerPattern[nIndexPattern]
							dictExtractedVars = dictExtractedVarsPerPattern[nIndexPattern]
							dictExtractedVarsConf = dictExtractedVarsConfPerPattern[nIndexPattern]

							listPropPattern = dict_POS_pattern_settings['proposition_pattern'][nIndexPattern][0]
							nTargetIndex = dict_POS_pattern_settings['proposition_pattern'][nIndexPattern][1]

							#logger.info('*** pattern = ' + repr(listPropPattern) )
							#logger.info('' )
							#logger.info('' )
							#logger.info('' )

							# loop on each extraction for this sent
							listPropSet = []
							listPropSetConf = []
							for nMatchIndex in range(len(dictExtractedVars[nIndexDoc][nSentIndex])) :

								#logger.info( '  match ' + str(nMatchIndex) )

								# get extraction vars
								# listExtractedVars = [ ( var_type, var_name, graph_address, collapsed_graph_addresses[], { dep : [ var_name, ... ] }, pattern_index ), ... ]
								listExtractedVars = dictExtractedVars[nIndexDoc][nSentIndex][nMatchIndex]
								nConf = dictExtractedVarsConf[nIndexDoc][nSentIndex][nMatchIndex]

								listResult = openiepy.comp_sem_lib.generate_proposition_set_from_extraction(
									list_extracted_vars = listExtractedVars,
									dep_graph = dictDepGraphs[nIndexDoc][nSentIndex],
									proposition_pattern = listPropPattern,
									dict_displaced_context = dict_POS_pattern_settings['displaced_context'],
									dict_sem_drift = dict_POS_pattern_settings['semantic_drift_cost'],
									max_semantic_dist = dict_POS_pattern_settings['max_end_to_end_semantic_dist'],
									include_context = dict_POS_pattern_settings['include_context_in_prop'],
									dict_openie_config = dictAttribIEConfig )

								# add to prop set (avoiding any duplicates)
								if listResult != None :
									for tupleResult in listResult :
										if not tupleResult in listPropSet :
											listPropSet.append( tupleResult )
											listPropSetConf.append( nConf )

							# filter prop set for this sent (for this prop pattern target)
							if dict_POS_pattern_settings['filter_prop_strat'] in ['min_length','max_length'] :
								openiepy.comp_sem_lib.filter_proposition_set(
									list_proposition_set = listPropSet,
									list_proposition_set_conf = listPropSetConf,
									target_index = nTargetIndex,
									filter_strategy = dict_POS_pattern_settings['filter_prop_strat'],
									dict_index_stoplist_prefix = dict_POS_pattern_settings['prop_stoplist_prefix'],
									dict_index_stoplist_suffix = dict_POS_pattern_settings['prop_stoplist_suffix'],
									dict_openie_config = dictAttribIEConfig )

							# serialize propositional structures (per pattern)
							for nIndexProp in range(len(listPropSet)) :
								tupleResult = listPropSet[nIndexProp]
								nConf = listPropSetConf[nIndexProp]
								( listPhraseText, listHeadText, listPhrasesProposition, listHeadProposition, nPatternIndex, listPattern ) = tupleResult
								dictDocumentPropositionSetsPerPattern[nIndexPattern].append( ( str(nIndexDoc), listPhraseText, nPatternIndex, nConf, listPattern, listHeadText ) )

							# also aggregate all patterns together
							listPropSetAggregate.extend( listPropSet )
							listPropSetConfAggregate.extend( listPropSetConf )

						# filter aggregate prop set (prop subsumption)
						if dict_POS_pattern_settings['filter_prop_strat'] == 'prop_subsumption' :
							openiepy.comp_sem_lib.filter_proposition_set(
								list_proposition_set = listPropSetAggregate,
								list_proposition_set_conf = listPropSetConfAggregate,
								target_index = None,
								filter_strategy = dict_POS_pattern_settings['filter_prop_strat'],
								dict_index_stoplist_prefix = dict_POS_pattern_settings['prop_stoplist_prefix'],
								dict_index_stoplist_suffix = dict_POS_pattern_settings['prop_stoplist_suffix'],
								dict_openie_config = dictAttribIEConfig )

						# serialize propositional structures (aggregated)
						for nIndexProp in range(len(listPropSetAggregate)) :
							tupleResult = listPropSetAggregate[nIndexProp]
							nConf = listPropSetConfAggregate[nIndexProp]
							( listPhraseText, listHeadText, listPhrasesProposition, listHeadProposition, nPatternIndex, listPattern ) = tupleResult
							listDocumentPropositionSetsAggregated.append( ( str(nIndexDoc), listPhraseText, nPatternIndex, nConf, listPattern, listHeadText ) )

			#
			# EXTRACT : save extracted propositions to file
			#

			if strMode == 'extract' :

				#
				# save extractions to disk (plain text report and encoded)
				# note: score is always 1 as we have no meaningful way to score propositions at this stage
				#   <sent-text>
				#   <sent-index> tab <arg> tab <rel> tab <arg> tab <score>
				#   ...
				#

				logger.info( '\n\nSAVE PROPOSITIONS\n' )

				# save propositions for each set of patterns
				for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
					logger.info( 'pattern : ' + str(nIndexPattern) )

					listDocumentPropositionSets = dictDocumentPropositionSetsPerPattern[nIndexPattern]

					strResultFile = strDataset + os.sep + strExtractFile + '_' + str(nIndexPattern) + '.txt'
					logger.info( 'result file: ' + strResultFile )
					writeHandle = codecs.open( strResultFile, 'w', 'utf-8', errors = 'replace' )

					for nIndexDoc in sorted( dictDepGraphs.keys() ) :
						writeHandle.write( dictText[nIndexDoc] + '\n' )

						# loop on all propositions that refer to this document
						listPropsGenerated = []
						for (strIndexDoc, listPhraseText, nPatternIndex, nConf, listPropPattern, listHeadText ) in listDocumentPropositionSets :
							if strIndexDoc == str(nIndexDoc) :

								# only write a prop once if we have seen it before from another pattern
								if not listPhraseText in listPropsGenerated :
									listPropsGenerated.append( listPhraseText )

									# serialize result
									writeHandle.write( strIndexDoc + '\t' )
									for nIndexPhrase in range(len(listPhraseText)) :
										writeHandle.write( '"' + listPhraseText[nIndexPhrase] + '"' )
										writeHandle.write( '\t' )
									writeHandle.write( str(nConf) + '\n' )

					writeHandle.close()

					if bOutputAnnotatedProp == True :

						strResultFile = strDataset + os.sep + 'annotated-' + strExtractFile + '_' + str(nIndexPattern) + '.txt'
						logger.info( 'result file: ' + strResultFile )
						writeHandle = codecs.open( strResultFile, 'w', 'utf-8', errors = 'replace' )

						for nIndexDoc in sorted( dictDepGraphs.keys() ) :
							writeHandle.write( dictText[nIndexDoc] + '\n' )

							# loop on all propositions that refer to this document
							listPropsGenerated = []
							for (strIndexDoc, listPhraseText, nPatternIndex, nConf, listPropPattern, listHeadText ) in listDocumentPropositionSets :
								if strIndexDoc == str(nIndexDoc) :

									# only write a prop once if we have seen it before from another pattern
									if not listPhraseText in listPropsGenerated :
										listPropsGenerated.append( listPhraseText )

										# serialize result
										writeHandle.write( strIndexDoc + '\t' )

										for nIndexPhrase in range(len(listPhraseText)) :
											writeHandle.write( '"' + listPhraseText[nIndexPhrase] + '"' )
											writeHandle.write( '\t' )

										for nIndexHead in range(len(listHeadText)) :
											writeHandle.write( '"' + listHeadText[nIndexHead] + '"' )
											writeHandle.write( '\t' )

										writeHandle.write( str(nConf) + '\t' )

										writeHandle.write( '{' )
										for nPropIndex in range(len(listPropPattern)) :
											strPropType = listPropPattern[nPropIndex]
											writeHandle.write( strPropType )
											if nPropIndex < len(listPropPattern)-1 :
												writeHandle.write( ',' )
										writeHandle.write( '}' )

										writeHandle.write( '\n' )

						writeHandle.close()

				# save propositions for aggregated patterns
				strResultFile = strDataset + os.sep + strExtractFile
				logger.info( 'result file (aggregated): ' + strResultFile )
				writeHandle = codecs.open( strResultFile, 'w', 'utf-8', errors = 'replace' )

				for nIndexDoc in sorted( dictDepGraphs.keys() ) :
					writeHandle.write( dictText[nIndexDoc] + '\n' )

					# loop on all propositions that refer to this document
					listPropsGenerated = []
					for (strIndexDoc, listPhraseText, nPatternIndex, nConf, listPropPattern, listHeadText ) in listDocumentPropositionSetsAggregated :
						if strIndexDoc == str(nIndexDoc) :

							# only write a prop once if we have seen it before from another pattern
							if not listPhraseText in listPropsGenerated :
								listPropsGenerated.append( listPhraseText )

								# serialize result
								writeHandle.write( strIndexDoc + '\t' )
								for nIndexPhrase in range(len(listPhraseText)) :
									writeHandle.write( '"' + listPhraseText[nIndexPhrase] + '"' )
									writeHandle.write( '\t' )
								writeHandle.write( str(nConf) + '\n' )

				writeHandle.close()

				if bOutputAnnotatedProp == True :

					strResultFile = strDataset + os.sep + 'annotated-' + strExtractFile
					logger.info( 'result file (aggregated): ' + strResultFile )
					writeHandle = codecs.open( strResultFile, 'w', 'utf-8', errors = 'replace' )

					for nIndexDoc in sorted( dictDepGraphs.keys() ) :
						writeHandle.write( dictText[nIndexDoc] + '\n' )

						# loop on all propositions that refer to this document
						listPropsGenerated = []
						for (strIndexDoc, listPhraseText, nPatternIndex, nConf, listPropPattern, listHeadText ) in listDocumentPropositionSetsAggregated :
							if strIndexDoc == str(nIndexDoc) :

								# only write a prop once if we have seen it before from another pattern
								if not listPhraseText in listPropsGenerated :
									listPropsGenerated.append( listPhraseText )

									# serialize result
									writeHandle.write( strIndexDoc + '\t' )

									for nIndexPhrase in range(len(listPhraseText)) :
										writeHandle.write( '"' + listPhraseText[nIndexPhrase] + '"' )
										writeHandle.write( '\t' )

									for nIndexHead in range(len(listHeadText)) :
										writeHandle.write( '"' + listHeadText[nIndexHead] + '"' )
										writeHandle.write( '\t' )

									writeHandle.write( str(nConf) + '\t' )

									writeHandle.write( '{' )
									for nPropIndex in range(len(listPropPattern)) :
										strPropType = listPropPattern[nPropIndex]
										writeHandle.write( strPropType )
										if nPropIndex < len(listPropPattern)-1 :
											writeHandle.write( ',' )
									writeHandle.write( '}' )

									writeHandle.write( '\n' )

					writeHandle.close()

			#
			# FILTER : filter templates using ground truth, save templates to file
			#

			if strMode == 'filter' :

				logger.info( '\n\nAPPLY RELEVANCE FEEDBACK\n' )

				if listGroundTruth == None :
					raise Exception( 'cannot process feedback loop without a ground truth file for feedback (None)' )

				if nFeedbackStartIndex == -1 :
					nFeedbackStartIndex = 0
				if nFeedbackEndIndex == -1 :
					nFeedbackEndIndex = len(listGroundTruth)

				logger.info( 'feedback used ' + repr( (nFeedbackStartIndex,nFeedbackEndIndex) ) )

				# apply ground truth relevance filter to filter each patterns's set of templates
				for nIndexPattern in range(len(dict_POS_pattern_settings['proposition_pattern'])) :
					logger.info( 'pattern : ' + str(nIndexPattern) )

					listDocumentPropositionSets = dictDocumentPropositionSetsPerPattern[nIndexPattern]
					listParsedExtractionPatterns = dictParsedExtractionPatternsPerPattern[nIndexPattern]

					# remove from listParsedExtractionPatterns any templates that generated an incorrect extraction
					openiepy.comp_sem_lib.filter_open_extraction_templates_using_relevance_feedback(
						list_parsed_patterns = listParsedExtractionPatterns,
						list_doc_set_of_propositions = listDocumentPropositionSets,
						list_relevance_feedback = listGroundTruth[nFeedbackStartIndex:nFeedbackEndIndex],
						dict_openie_config = dictAttribIEConfig )

					# write open pattern templates to disk
					strNewTemplateFile = strDataset + os.sep + strFilteredTemplateFile + '_' + str(nIndexPattern) + '.txt'
					logger.info( 'writing open extraction templates to file ' + strNewTemplateFile )
					writeHandle = codecs.open( strNewTemplateFile, 'w', 'utf-8', errors = 'replace' )
					for strPattern in listOpenExtractionPatternsTotal :
						writeHandle.write( strPattern + '\n' )
					writeHandle.close()

	except :
		logger.exception( 'eval_attrib_ie main() exception' )
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
	sys.stderr.flush()
	sys.stdout.flush()
	sys.exit(0);
