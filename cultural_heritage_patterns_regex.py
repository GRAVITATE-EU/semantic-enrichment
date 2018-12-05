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
	// Created Date : 2016/08/15
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


# using re.UNICODE | re.DOTALL so we all newlines which will appear in the text. the POS tagging will label them as such if this is important.

# use \A to match from start of tagged sent fragment
# order regex in order of match attempt (match most specific regex first)

# (?:...) = (?:JJ|NN|NNP) = group that does not return a result (use as part of a returning parent group)
# (...){0,2} = must have 0 to 2 matches for this group
# \w* = any number of alphanumeric chars
# \S* = any number of non whitespace chars
# \s\S* = any sequence of chars
# .* = any sequence of chars except newline
# .*? is a non-greedy version of .* matching as few as possible characters (e.g. useful with a sunsequent group match)
# \A = start of string
# \Z = end of string
# x|yy|zzz = allowed alternatives for a group (matched in strict left to right sequence with first match taken i.e. not greedy)
# regex https://docs.python.org/2/library/re.html
# for sent regex matches use [^)]* not \S* so we do not match into other sent subtrees. the () are escaped out (to -LRB- and -RRB-) on serialization prior to regex

import re

# any full alpha numeric identifier (i.e. not text with only characters or only digits) OR sequence of text initials that can end with a period 'A.B.' OR sequence of alpha numeric that cannot end with a period 'A.2'
# note: this means we will replace NAMESPACE and will need to handle currency explicitly (e.g. £15.67) but we can capture many CH identifier types
# note: these regex assume pretty well formatted text where sent periods have a space after them.
# note: tokenization will make
#       cited in 1888,0601.580.d. ==> 1888,0601.580.d
#       s.e. middleton ==> s.e.
initials = ur'([a-zA-Z]\.(( ){0,1}[a-zA-Z]\.){0,5})'
alpha_numeric = ur'([a-zA-Z]+[a-zA-Z0-9\:\-\.\,]*([0-9]+|[0-9]+[a-zA-Z0-9\:\-\.\,]*[a-zA-Z]+)|[0-9]+[a-zA-Z0-9\:\-\.\,]*([a-zA-Z]+|[a-zA-Z]+[a-zA-Z0-9\:\-\.\,]*[0-9]+))'
alpha_numeric_or_digits = ur'(' + alpha_numeric + ur'|[0-9]+|[IVXLCDMivxlcdm]+)'

# roman numeral best guess. will not match I or i as it will overmatch with normal text.
roman_numeral = ur'([VXLCDMvxlcdm][IVXLCDMivxlcdm]{1,}|[IVXLCDMivxlcdm]{2,})'

#
# Token identification patterns (from free text)
#

'''
#
# list of linguistic types we want to be returned from matches (an explicit list is needed to differentiate from POS labels)
#
listLinguisticLabels = [
	'CAT_INDEX', 'FIGURE', 'TABLE', 'DOC_SECTION', 'DATABASE_ENTRY', 'REFER', 'INITIAL', 'ALPHA_ID',
	'REF', 'MEASUREMENT', 'SIZE_TYPE', 'SIZE_CONTEXT', 'SIZE_VALUE','SIZE_UNIT', 'REL_SIZE', 'SUBJECT',
	],
'''


# regex patterns based on text patterns (i.e. not POS tagged text) to identify tokens that should have a special POS tag
# note: these regex are applied first to the untokenized text (e.g. 'blah blah abc blah') then later to the tokenized patterns (e.g. 'abc'). as such pattern should not expect a space at start.
# note: look ahead and behind to avoid '__' (token replacement characters) and [A-Za-z0-9\-] (matches embedded within another valid token)
# note: the order these are executed is random so regex patterns must not be able to match each other otherwise non-deterministic matches will result
#

look_behind_tag = ur'\A.*?(?<!__)(?<![A-Za-z0-9\-])'
look_ahead_tag = ur'(?!__)(?![A-Za-z0-9\-])'

dictTagPatterns = {

	# citation entities regex for formal cultural heritage descriptions to be annotated as POS tags
	# using humanities style of author-date notation
	# see https://en.wikipedia.org/wiki/Parenthetical_referencing
	# see https://docs.python.org/2/library/re.html
	#<label> = <alphanumeric>:-
	#<index> = 
	#	Inv. no. <label>
	#	Cat. no. <label>
	#	Cat. nos <label>, <label>, ... and <label>
	#<figure> = 
	#	Fig. <label>
	#	Figs <label>, <label> and <label>
	#	Figs <label>; <label> and <label>
	#<section> =
	#	[SCE|ABV|CVA|LIMC|pl.|no.] <label> [<page>|top|bottom]
	#	[SCE|ABV|CVA|LIMC|pl.|no.] <label> <section_num>[,] [<page>|top|bottom]
	#	CVA|LIMC are well know CH databases that get referenced
	#<page> = number
	#<section_num> = number of roman numeral
	#
	#<citation> =
	#	(<entry_list>)
	#	(cf: ... <entry_list>)
	#	cf: ... <entry_list>
	#
	# <refer> is just the textual term indicating a ref folows, not the ref itself
	# <identifier> MUST be preceeded by a space and MUST NOT match the other patterns so we include a long negative lookbehind clause to avoid matches with the other regex
	#

	'citation_cat_index_regex' : (
		re.compile( look_behind_tag + ur'(?P<CAT_INDEX>(inv\.|cat\.|frag.|frags|fragment|fragments) (no |no\. |nos ){0,1}' + alpha_numeric_or_digits + ur'((,|;|=)( ){0,1}' + alpha_numeric_or_digits + ur'){0,5}( and ' + alpha_numeric_or_digits + ur'){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'CAT_INDEX' ),
	'citation_figure_regex' : (
		re.compile( look_behind_tag + ur'(?P<FIGURE>(fig\.|fig\. |figure |figs |figures )' + alpha_numeric_or_digits + ur'(,( ){0,1}' + alpha_numeric_or_digits + ur'){0,5}( and ' + alpha_numeric_or_digits + ur'){0,1}( top| bottom| left| right){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'FIGURE' ),
	'citation_table_regex' : (
		re.compile( look_behind_tag + ur'(?P<TABLE>(table |tables )' + alpha_numeric_or_digits + ur'(,( ){0,1}' + alpha_numeric_or_digits + ur'){0,5}( and ' + alpha_numeric_or_digits + ur'){0,1}( top| bottom| left| right){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'TABLE' ),
	'citation_doc_section_regex' : (
		re.compile( look_behind_tag + ur'(?P<DOC_SECTION>(sce|sce,|page|p\.|pp|pl\.|no\.|nos\.|nos|note|no|section) ' + alpha_numeric_or_digits + ur'(,( ){0,1}' + alpha_numeric_or_digits + ur'){0,5}( and ' + alpha_numeric_or_digits + ur'){0,1}( top| bottom| left| right){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DOC_SECTION' ),
	'citation_database_entry_regex' : (
		re.compile( look_behind_tag + ur'(?P<DATABASE_ENTRY>(abv,|abv|cva,|cva|limc,|limc) ' + alpha_numeric_or_digits + ur'(,( ){0,1}' + alpha_numeric_or_digits + ur'){0,5}( and ' + alpha_numeric_or_digits + ur'){0,1}( top| bottom| left| right){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DATABASE_ENTRY' ),
	'refer' : (
		re.compile( look_behind_tag + ur'(?P<REFER>(cf\.|ref\.|cf|ref))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'REFER' ),
	'initials' : (
		re.compile( look_behind_tag + ur'(?P<INITIAL>' + initials + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'INITIAL' ),
	'et_al' : (
		re.compile( look_behind_tag + ur'(?P<ET_AL>et al\.)' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'ET_AL' ),
	'vol' : (
		re.compile( look_behind_tag + ur'(?P<VOL>(vol\.|volume|vol|issue) ' + alpha_numeric_or_digits + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'VOL' ),
	'class' : (
		re.compile( look_behind_tag + ur'(?P<CLASS>(class|type|category) ' + alpha_numeric_or_digits + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'CLASS' ),
	'title' : (
		re.compile( look_behind_tag + ur'(?P<TITLE>(prof\.|prof|dr|miss|mrs|mr))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'TITLE' ),
	'alpha_id' : (
		re.compile( look_behind_tag + ur'(?<!no |p\. )(?<!sce |abv |cva |pl\. |no\. |nos )(?<!limc |sce, |abv, |cva, |nos\. |note |fig\. |figs |fig\. )(?<!limc, |table )(?<!figure |tables )(?<!section |figures )(?P<ALPHA_ID>' + alpha_numeric + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'ALPHA_ID' )
}

dictTagDependancyParseMapping = {
	'CAT_INDEX' : 'CD',
	'FIGURE' : 'CD',
	'TABLE' : 'CD',
	'DOC_SECTION' : 'CD',
	'DATABASE_ENTRY' : 'CD',
	'ALPHA_ID' : 'CD',
	'VOL' : 'CD',
	'CLASS' : 'CD',
	'MEASUREMENT' : 'CD',

	'INITIAL' : 'SYM',
	'TITLE' : 'SYM',
	'ET_AL' : 'SYM',
	'REFER' : 'SYM',

	'NAMESPACE' : '#',
	'URI' : '#',
	'BIB' : '#',
	'CITE' : '#',

}

#
# Construct domain vocab patterns
# note: NOT USED
#

# relative size
vocab = ( 'small','large','narrow','wide(r)?','thin(ner)?','thick(er)?',
	'lifesize(d)?','life - size(d)?',
	'over lifesize(d)?', 'over - lifesize(d)?', 'over life - size(d)?', 'over - lifesize(d)?'
	'under lifesize(d)?', 'under - lifesize(d)?', 'under life - size(d)?', 'under - lifesize(d)?'
	'thumb size(d)?', 'thumb - size(d)?'
	)
vocab_pattern = None
for vocab_phrase in vocab :
	if vocab_pattern == None :
		vocab_pattern = ur'('
	else :
		vocab_pattern = vocab_pattern + ur'|'
	listVocabTokens = vocab_phrase.split( ' ' )
	for nIndexVocab in range(len(listVocabTokens)) :
		if nIndexVocab > 0 :
			vocab_pattern = vocab_pattern + ur' '
		vocab_pattern = vocab_pattern + ur'\(\S* ' + listVocabTokens[nIndexVocab] + '\)'
relative_size_vocab = vocab_pattern + ur')'

# size types
vocab = ( 'height','width','diameter','circumference','radius','weight','mass','vol(ume)?','size')
vocab_pattern = None
for vocab_phrase in vocab :
	if vocab_pattern == None :
		vocab_pattern = ur'('
	else :
		vocab_pattern = vocab_pattern + ur'|'
	listVocabTokens = vocab_phrase.split( ' ' )
	for nIndexVocab in range(len(listVocabTokens)) :
		if nIndexVocab > 0 :
			vocab_pattern = vocab_pattern + ur' '
		vocab_pattern = vocab_pattern + ur'\(\S* ' + listVocabTokens[nIndexVocab] + '\)'
size_type_vocab = vocab_pattern + ur')'

# unit types for common size metrics (length, mass, volume)
# source: QUDT
vocab = ( 'mm','millimet(er|re)(s)?','millimet(er|re)(s)?','cm','centimet(er|re)(s)?','m','met(er|re)(s)?','km','kilomet(er|re)(s)?','mile(s)?','ft','foot|feet','in','inch(es)','yd','yard(s)?',
	'g','gram(s)?','kg','kilogram(s)?','ton(s)','metric ton(s)','tonne(s)',
	'L','litre(s)?','cm\^3','cubic met(er|re)(s)?','ft\^3','cubic foot|feet','m\^3','cubic met(er|re)(s)?','yd\^3','cubic yard(s)?')
vocab_pattern = None
for vocab_phrase in vocab :
	if vocab_pattern == None :
		vocab_pattern = ur'('
	else :
		vocab_pattern = vocab_pattern + ur'|'
	listVocabTokens = vocab_phrase.split( ' ' )
	for nIndexVocab in range(len(listVocabTokens)) :
		if nIndexVocab > 0 :
			vocab_pattern = vocab_pattern + ur' '
		vocab_pattern = vocab_pattern + ur'\(\S* ' + listVocabTokens[nIndexVocab] + '\)'
size_unit_vocab = vocab_pattern + ur')'


#
# Linguistic guidelines for POS analysis
#   Entity class = Noun (e.g. author)
#   Entity instance = Proper Noun (e.g. Joe Bloggs)
#   Relationship = Transitive verb (e.g. part of)
#   Attribute class = Intransitive verb
#   Attribute of entity instance = Adjective
#   Attribute of relationship instance = Adverb
# note: NOT USED this was heading towards discourse analysis originally
#

numeric_list = ur'( \(((CD|ALPHA_ID) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4} \(((CD|ALPHA_ID) [^)]*|NP ' + roman_numeral + ur')\)'
numeric_list_optional = ur'( \(((CD|ALPHA_ID) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4}'

numeric_or_doc_section_list = ur'( \(((CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4} \(((CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)'
numeric_or_doc_section_list_optional = ur'( \(((CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4}'

numeric_or_doc_section_list_with_names = ur'( \(((NP|NN|NNS|INITIAL|CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4} \(((NP|NN|NNS|INITIAL|CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)'
numeric_or_doc_section_list_with_names_optional = ur'( \(((NP|NN|NNS|INITIAL|CD|ALPHA_ID|DOC_SECTION) [^)]*|NP ' + roman_numeral + ur')\)( \(, ,\)){0,1}){0,4}'

museum_name = ur'(\(((NNP|NNPS|NN|NNS|CC|FW) [^)]*|IN of)\) ){0,10}\(\w* (museum|gallery|institute|bm|oxford|athens|cambridge|fitzwilliam|toronto|leiden|ashmolean|london|ucl|paris|louvre|boston|york|berlin|olympia|egypt|southampton|durham|herakleon|memphis)\)( \(((NNP|NNPS|NN|NNS|CC|FW) [^)]*|IN of)\)){0,10}'

# <author-list> = Heilman, J. M. and West, A. G. or Middleton, S.E. et al.
# repeats of '[dr] initial name' OR 'name, initial' OR '[dr] name,'
author_list = ur'((\(INITIAL [^)]*\) \((NNP|NNPS) [^)]*\) |\((NNP|NNPS) [^)]*\) \(, [^)]*\) \(INITIAL [^)]*\) |\((NNP|NNPS) [^)]*\) \(, [^)]*\) )){0,10}(\(CC [^)]*\) ){0,1}(\(ET_AL [^)]*\)|\(INITIAL [^)]*\) \((NNP|NNPS) [^)]*\)|\((NNP|NNPS) [^)]*\) \(, [^)]*\) \(INITIAL [^)]*\)|\((NNP|NNPS) [^)]*\))'
author_list = ur'(((\(TITLE [^)]*\) ){0,1}\(INITIAL [^)]*\) \((NNP|NNPS) [^)]*\) |\((NNP|NNPS) [^)]*\) \(, [^)]*\) \(INITIAL [^)]*\) |(\(TITLE [^)]*\) ){0,1}\((NNP|NNPS) [^)]*\) \(, [^)]*\) )){0,10}(\(CC [^)]*\) ){0,1}(\(ET_AL [^)]*\)|(\(TITLE [^)]*\) ){0,1}\(INITIAL [^)]*\) \((NNP|NNPS) [^)]*\)|\((NNP|NNPS) [^)]*\) \(, [^)]*\) \(INITIAL [^)]*\)|(\(TITLE [^)]*\) ){0,1}\((NNP|NNPS) [^)]*\))'

# <vol_entry> = 1 or 1(2) or vol. 1, issue 2
vol_entry = ur'(\((CD|ALPHA_ID) [^)]*\)( \(-LRB- [^)]*\) \((CD|ALPHA_ID) [^)]*\) \(-RRB- [^)]*\)){0,1}|\(VOL [^)]*\)( \(, ,\)){0,1}( \(VOL [^)]*\)){0,1})'

# catalogue id list
cat_list = ur'\((CD|CAT_INDEX|ALPHA_ID) [^)]*\)( \(, ,\) \((CD|CAT_INDEX|ALPHA_ID) [^)]*\)){0,50}( \(CC [^)*]\) \((CD|CAT_INDEX|ALPHA_ID) [^)]*\)){0,1}'

# regex patterns for labelling sequences of POS tags in a sent tree
# regex works on serialized sent Trees with () escaped using stanford standard -LRB- and -RRB-
# e.g. (S  (DT This) (NN head) (VBD was) (VVN assigned) (IN by) (NP Gjerstad) (-LRB- -LRB-) (DOC_SECTION SCE IV: 2, 108) (-RRB- -RRB-))
# note: there is no pre-defined execution order for entity pattern groups.
# note: order of execution of regex per pattern group is strictly sequential (top to bottom of list) so add the most permissive matches last in list. any text matched is remove from the text available for matching. 

dictIdentifierPatterns = {

	'reference' : [
		# Brown and Catling 1975, 53
		# Karageorghis, Vassilika and Wilson 1999, 66 Cat. no. 118
		# Karageorghis 1993, 31-3, 50
		# Hermary 1991, pl. XXXIX:b
		# cf. Matthaeus 1985, 100 note 65, pl. 7.155

		# <author-list> <year>, <volume>(<issue>), <page>
		# <page> = DOC_SECTION
		# <issue>, <volume> = number
		# <year> = 1999 or (2017)
		# <author-list> = Heilman, J. M. and West, A. G.
		# often presented in () e.g. (Middleton 2017)

		# museum reference
		# <museum-name> = Boston, Museum of Fine Arts
		# <museum-name> ( <year> ) [,] <catalogue-id>, <catalogue-id> and <catalogue-id>
		# <museum-name> [,] <year> [,] <catalogue-id>, <catalogue-id> and <catalogue-id>
		# <museum-name> <catalogue-id>, <catalogue-id> and <catalogue-id>
		re.compile( ur'\A.*? (?P<CITE>(\((NNP|NNPS|NN|NNS) [^)]*\) ){1,5}\(, ,\) ' + museum_name + ur' \(-LRB- [^)]*\) \(CD [^)]*\) \(-RRB- [^)]*\)( \(, ,\)){0,1} ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),
		re.compile( ur'\A.*? (?P<CITE>(\((NNP|NNPS|NN|NNS) [^)]*\) ){1,5}\(, ,\) ' + museum_name + ur'( \(, [^)]*\)){0,1} \(CD [^)]*\)( \(, [^)]*\)){0,1} ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),
		re.compile( ur'\A.*? (?P<CITE>(\((NNP|NNPS|NN|NNS) [^)]*\) ){1,5}\(, ,\) ' + museum_name + ur' ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),

		# <museum-name> = City Art Gallery & Museum, British Museum, Museum of Fine Arts
		# <museum-name> ( <year> ) [,] <catalogue-id>, <catalogue-id> and <catalogue-id>
		# <museum-name> [,] <year> [,] <catalogue-id>, <catalogue-id> and <catalogue-id>
		# <museum-name> <catalogue-id>, <catalogue-id> and <catalogue-id>
		re.compile( ur'\A.*? (?P<CITE>' + museum_name + ur' \(-LRB- [^)]*\) \(CD [^)]*\) \(-RRB- [^)]*\)( \(, ,\)){0,1} ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),
		re.compile( ur'\A.*? (?P<CITE>' + museum_name + ur'( \(, [^)]*\)){0,1} \(CD [^)]*\)( \(, [^)]*\)){0,1} ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),
		re.compile( ur'\A.*? (?P<CITE>' + museum_name + ur' ' + cat_list + ur')', re.UNICODE | re.DOTALL | re.IGNORECASE ),

		# citation
		# ( <author-list> [,] <year> )
		re.compile( ur'\A.*? (?P<CITE>\(-LRB- [^)]*\) ' + author_list + ur'( \(, ,\)){0,1} \(CD [^)]*\) \(-RRB- [^)]*\))', re.UNICODE | re.DOTALL | re.IGNORECASE ),

		# catalogue database references
		# <database_name> [, <volume> ( <issue> ) ] [, <entry_name>] [, <page>]
		re.compile( ur'\A.*? (?P<BIB>\(DATABASE_ENTRY [^)]*\)( (\(, ,\) ){0,1}' + vol_entry + ur'){0,1}( (\(, ,\) ){0,1}\((NNP|NNPS) [^)]*\)){0,1}( (\(, ,\) ){0,1}\(DOC_SECTION [^)]*\)){0,1})', re.UNICODE | re.DOTALL | re.IGNORECASE ),

		# bib entry
		# <author-list> ( <year> ) [, <volume> ( <issue> ) ] [, <class>] [, <page>] [, <figure>]
		re.compile( ur'\A.*? (?P<BIB>' + author_list + ur' \(-LRB- [^)]*\) \(CD [^)]*\) \(-RRB- [^)]*\)( (\(, ,\) ){0,1}' + vol_entry + ur'){0,1}( (\(, ,\) ){0,1}\(CLASS [^)]*\)){0,1}( (\(, ,\) ){0,1}\(DOC_SECTION [^)]*\)){0,1}( (\(, ,\) ){0,1}\((CAT_INDEX|FIGURE|TABLE) [^)]*\)){0,1})', re.UNICODE | re.DOTALL | re.IGNORECASE ),

		# bib entry = <author-list> <year> [, <volume> ( <issue> ) ] [, <class>] [, <page>] [, <figure>]
		re.compile( ur'\A.*? (?P<BIB>' + author_list + ur' \(CD [^)]*\)( (\(, ,\) ){0,1}' + vol_entry + ur'){0,1}( (\(, ,\) ){0,1}\(CLASS [^)]*\)){0,1}( (\(, ,\) ){0,1}\(DOC_SECTION [^)]*\)){0,1}( (\(, ,\) ){0,1}\((CAT_INDEX|FIGURE|TABLE) [^)]*\)){0,1})', re.UNICODE | re.DOTALL | re.IGNORECASE ),
	]

}

dictAttributePatterns = {

	'measurement' : [
		# Preserved height: 9,8 cm                                 == Preserved/VVN height/NN :/: 9/CD ,/, 8/CD cm/NN ==> (S (VVN Preserved) (NN height) (: :) (CD 14) (, ,) (CD 2) (NN cm))
		# Restored height of the head: 39 cm                       == Restored/VVN height/NN of/IN the/DT head/NN :/: 39/CD cm/NN

		# over-lifesized statue                                    == over/RB -/: lifesized/JJ statue/NN ==> (RB over) (: -) (JJ lifesized) (NN statue)
		# thumb size Fist diameter                                 == thumb/NN size/NN Fist/NN diameter/NN ==> (S (NN thumb) (NN size) (NN Fist) (NN diameter))
		# the narrow forehead                                      == the/DT narrow/JJ forehead/NN ==> (DT the) (JJ narrow) (NN forehead)
		# its small size                                           == its/PP$ small/JJ size/NN ==> (PP$ its) (JJ small) (NN size)
		# a thinner tunic                                          == a/DT thinner/JJR tunic/NN ==> (DT a) (JJR thinner) (NN tunic)

		# its [<rb> -] <size-adj/nn> size
		# [<rb> -] <size-adj/nn> <artifact-nn>

		re.compile( ur'\A.*? (?P<MEASUREMENT>(?P<SIZE_TYPE>(\(VVN \w*\) ){0,1}' + size_type_vocab + ')( (?P<SIZE_CONTEXT>(\(\w* \w*\) ){0,4}\(\w* \w*\))){0,1} (\(\S* [:\-=>,;]\) ){0,1}(?P<SIZE_VALUE>(\(\S* [0-9,.;]*\) ){0,2}\(\S* [0-9,.;]*\)) (?P<SIZE_UNIT>' + size_unit_vocab + '))', re.UNICODE | re.DOTALL | re.IGNORECASE ),
		re.compile( ur'\A.*? (?P<MEASUREMENT>(?P<REL_SIZE>' + relative_size_vocab + ') (?P<SUBJECT>(\(NN \S*\) ){0,4}\(NN \S*\)))', re.UNICODE | re.DOTALL | re.IGNORECASE )

		]
}


#
# Stanford ReVerb style patterns for extracting bootstrap seed_tuples to capture reliable arg and rel tuples
# seed_tuples are used later to create a sent set with all lexical combinations of arg and rel for input to create a set of open pattern templates for subsequent information extraction
# ReVerb = {arg} {rel} {arg}
# {rel} = V | VP | VW*P
# V = verb + optional particle (base, past, present) + optional adverb
# P = preposition, particle, inf. marker
# W = noun, adjective, adverb, pronoun, determiner
# {arg} = proper noun phrase (more reliable than noun or proper noun patterns)
# note: {prep} and then {rel} are matched first to avoid {arg} where then noun is in fact part of a relation (e.g. made a deal with -> deal is a noun)
# ReVerb takes longest match (so should be greedy) and merges adjacent sequences of argument and relations
#
# ReVerb CITE: Anthony Fader, Stephen Soderland, and Oren Etzioni. 2011. Identifying relations for open information extraction. In Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP '11). Association for Computational Linguistics, Stroudsburg, PA, USA, 1535-1545
#
listReVerbExecutionOrder = [ 'PREPOSITION', 'RELATION', 'PRONOUN', 'ARGUMENT', 'NUMERIC' ]

# Revised - ReVerb without the adverbs and adjectives.
# this means relation terms usually have a nice branch with a clear head (avoids rels made up of siblings). this in turn means seed matches sub-graph OK.
# the adverbs and adjectives get picked up via dep graph walk as slot nodes and are reported via rel/arg collased branches.
# {rel} = V | VP | VW*P
# {arg} = A
# V = verb + optional particle (base, past, present) + optional adverb
# P = preposition, particle, inf. marker
# W = noun, pronoun, determiner
# A = adjective, noun, pronoun
# Pronoun include personal pronouns (PRP, PRP$) = 1, me, you, possessive pronouns (PP$) = her, ours and relative pronouns (WDT, WP, WP$) = who, which, that, whose, whom

dictReVerbPatterns = {

	'PREPOSITION' : [
		re.compile( ur'\A.*?(?P<PREPOSITION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}\((TO|IN) [^)]*\)( \((TO|IN) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

	# note: prior PREPOSITION matches will be replaced with (PREPOSITION          ) so expect a set of spaces followed by a single closing bracket
	'RELATION' : [
		#re.compile( ur'\A.*?(?P<RELATION>\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,20}( \((NN|NNS|PRP|PRP[$]|WP|WP[$]|WDT|DET|EX) [^)]*\)){0,20} \(PREPOSITION [ ]*\))', re.UNICODE | re.DOTALL ),
		#re.compile( ur'\A.*?(?P<RELATION>\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),

		# VP | VW*P
		re.compile( ur'\A.*?(?P<RELATION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,19}( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,20}( \((NN|NNS|PRP|PRP[$]|WP|WP[$]|WDT|DT|EX) [^)]*\)){0,20}(?= \(PREPOSITION [ ]*\)))', re.UNICODE | re.DOTALL ),

		# V
		re.compile( ur'\A.*?(?P<RELATION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,19}( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),
		],

	'ARGUMENT' : [
		#re.compile( ur'\A.*?(?P<ARGUMENT>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((NNP|NNPS|NN|NNS|PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\))( \((NNP|NNPS|NN|NNS|PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		re.compile( ur'\A.*?(?P<ARGUMENT>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((NNP|NNPS|NN|NNS) [^)]*\))( \((NNP|NNPS|NN|NNS) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# allow a adverb/adjective preceeded by a determiner to act as an argument e.g. the best
		re.compile( ur'\A.*?(?P<ARGUMENT>(\(DT [^)]*\) ){1,20}\((RB|RBR|JJ|JJR|JJS) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

	# numeric value: e.g. approx 10 dead
	'NUMERIC' : [
		re.compile( ur'\A.*?(?P<NUMERIC>(\((RB|RBR|RBS) [^)]*\) ){0,20}\(CD [^)]*\)( \((JJ|JJR|JJS) [^)]*\)){1,20})', re.UNICODE | re.DOTALL ),
		],

	'PRONOUN' : [
		re.compile( ur'\A.*?(?P<ARGUMENT>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\))( \((NNP|NNPS|NN|NNS|PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

}

#
# Seed tuple patterns to used when creating open extraction template patterns. Tuples checked in the strict order they appear here, so put most specific patterns first.
# Pattern checker get_seed_tuples_from_extractions() allows sequential matches of same type
# e.g. ARGUMENT RELATION RELATION ARGUMENT will match a sequence ARGUMENT RELATION ARGUMENT
# Argument and Pronoun are separated so we can make sure pronouns are not chained (which usually spans gramatical structures and is incorrect)
# Seed tuples chosen based on an analysis of POS patterns associated with entity description text sentences (CH and DBpedia)
#
listSeedTuples = [
	('ARGUMENT', 'RELATION', 'ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'PRONOUN', 'PREPOSITION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'PREPOSITION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'PREPOSITION', 'PRONOUN'),
	('ARGUMENT', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'PRONOUN'),
	('ARGUMENT', 'RELATION', 'MEASUREMENT'),

	('ARGUMENT', 'PREPOSITION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'PREPOSITION', 'RELATION', 'PRONOUN'),
	('ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('ARGUMENT', 'PREPOSITION', 'PRONOUN'),
	('ARGUMENT', 'PREPOSITION', 'MEASUREMENT'),

	('PRONOUN', 'RELATION', 'ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('PRONOUN', 'RELATION', 'PRONOUN', 'PREPOSITION', 'ARGUMENT'),
	('PRONOUN', 'RELATION', 'PREPOSITION', 'ARGUMENT'),
	('PRONOUN', 'RELATION', 'PREPOSITION', 'PRONOUN'),
	('PRONOUN', 'RELATION', 'ARGUMENT'),
	('PRONOUN', 'RELATION', 'PRONOUN'),
	('PRONOUN', 'RELATION', 'MEASUREMENT'),

	('RELATION', 'PREPOSITION', 'RELATION', 'ARGUMENT'),
	('RELATION', 'PREPOSITION', 'RELATION', 'PRONOUN'),
	('RELATION', 'ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('RELATION', 'PRONOUN', 'PREPOSITION', 'ARGUMENT'),
	('RELATION', 'PREPOSITION', 'ARGUMENT'),
	('RELATION', 'PREPOSITION', 'PRONOUN'),
	('RELATION', 'ARGUMENT'),
	('RELATION', 'PRONOUN'),
	('RELATION', 'MEASUREMENT'),

	('PREPOSITION', 'ARGUMENT', 'RELATION', 'ARGUMENT'),
	('PREPOSITION', 'ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('PREPOSITION', 'PRONOUN', 'RELATION', 'ARGUMENT'),
	('PREPOSITION', 'PRONOUN', 'PREPOSITION', 'ARGUMENT'),
	('PREPOSITION', 'ARGUMENT'),
	('PREPOSITION', 'PRONOUN'),
	('PREPOSITION', 'MEASUREMENT'),

	('RELATION'),
	('ARGUMENT'),
	('PRONOUN'),
]

# Prevent chains of PREPOSITION in seed tuples as these likely to be semantically incorrect
listPreventSequentialMatches = [
	'PREPOSITION', 'PRONOUN'
]

'''
setSeedTuples = set( [

	# arg rel
	('ARGUMENT', 'RELATION'),
	('ARGUMENT', 'RELATION', 'RELATION'),
	('ARGUMENT', 'RELATION', 'RELATION', 'RELATION'),

	# arg* rel(1) arg*
	('ARGUMENT', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	# arg rel(2) arg
	('ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	# arg rel(3) arg
	('ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'RELATION', 'RELATION', 'RELATION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

	# arg prep arg ...
	('ARGUMENT', 'PREPOSITION', 'ARGUMENT'),
	('ARGUMENT', 'PREPOSITION', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'PREPOSITION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),
	('ARGUMENT', 'PREPOSITION', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT', 'ARGUMENT'),

])
'''

# map PREP to 'rel' so we capture 'head of statue' which occurs a lot as a text statement without any other context (e.g. verb) 
dictSeedToTemplateMapping = {
	'RELATION' : 'rel',
	'PREPOSITION' : 'prep',
	'ARGUMENT' : 'arg',
	'PRONOUN' : 'arg',
	'NUMERIC' : 'num',
	'MEASUREMENT' : 'arg',
	}

#
# Dependency graph navigation restrictions
# Depending on the extracted variable type a different branch navigation path will be chosen to capture relevant dependent text under each branches root node. This captures the contextual text for each extracted variable.
#

# set of known graph dependency types for variable pretty print
setGraphDepTypes = set([ 'rel','arg','num','prep' ])

# graph dependency types to allow for collapsing different branch types
# when generating matched variable collapsed branched for pretty print later
dictCollapseDepTypes = {
	'rel' : set([
		'advmod', 'aux', 'auxpass',
		'cop', 'prt', 'det', 'neg',
		'nsubj', 'nsubjpass', 'dobj', 'xcomp', 'ccomp', 'iobj',
		'case', 'case:of', 'case:by',
		'compound', 'amod', 'nummod', 'appos',
		'cc', 'conj'
		]),
	'arg' : set([
		'amod', 'compound', 'det', 'neg', 'nummod', 'advmod', 'appos',
		'case', 'case:of', 'case:by',
		'relcl', 'nfincl',
		'cc', 'conj',
		# 'dep' removed as it allows # (which includes RT @screenname)
		]),
	'num' : set([
		'advmod', 'nmod', 'acl',
		'case',
		]),
	'prep' : set([
		'amod', 'compound', 'det', 'neg', 'nummod', 'advmod', 'appos',
		'case', 'case:of', 'case:by',
		'relcl', 'nfincl',
		'cc', 'conj',
		]),
}

# adverbs and adjectives to include as context (1 deep only in tree) since they can change the meaning of the primary variable (e.g. verb)
# when generating open information extraction patterns
listContextualDepTypes = [
	# adverbial clause modifier (verb modifier), adverbial modifier (adverb modifier), adjectival modifier (adjective modifier)
	'advcl', 'advmod', 'amod',
	# negation (negative context for noun), auxillary (context to verb), coordinating conjunction (context to preceeding conj)
	'aux', 'auxpass', 'neg', 'cc',
	# case (preposition associated with noun)
	'case', 'case:of', 'case:by'
	]


