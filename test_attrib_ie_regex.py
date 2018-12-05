# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
..
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
	// Created By : Stuart E. Middleton
	// Created Date : 2018/07/02
	// Created for Project: GRAVITATE
	//
	/////////////////////////////////////////////////////////////////////////
	//
	// Dependancies: None
	//
	/////////////////////////////////////////////////////////////////////////
	'''

AttribIE parsing structures

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

import re, openiepy

# any full alpha numeric identifier (i.e. not text with only characters or only digits) OR sequence of text initials that can end with a period 'A.B.' OR sequence of alpha numeric that cannot end with a period 'A.2'
# note: this means we will replace NAMESPACE and will need to handle currency explicitly (e.g. £15.67) but we can capture many CH identifier types
# note: these regex assume pretty well formatted text where sent periods have a space after them.
# note: tokenization will make
#       cited in 1888,0601.580.d. ==> 1888,0601.580.d
#       s.e. middleton ==> s.e.
initials = ur'([a-zA-Z]\.(( ){0,1}[a-zA-Z]\.){0,5})'
alpha_numeric = ur'([a-zA-Z]+[a-zA-Z0-9\:\-\.\,]*([0-9]+|[0-9]+[a-zA-Z0-9\:\-\.\,]*[a-zA-Z]+)|[0-9]+[a-zA-Z0-9\:\-\.\,]*([a-zA-Z]+|[a-zA-Z]+[a-zA-Z0-9\:\-\.\,]*[0-9]+))'
alpha_numeric_or_digits = ur'(' + alpha_numeric + ur'|[0-9]+|[IVXLCDMivxlcdm]+)'
months = ur'(january|jan|feburary|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|october|oct|november|nov|december|dec)'
days = ur'(monday|mon|tuesday|tues|wednesday|wed|thursday|thurs|friday|fri|saturday|sat|sundat|sun)'

# https://en.wikipedia.org/wiki/International_System_of_Units
si_unit = ur'(°C|degC|deg C|degree C|°F|degF|deg F|degree F|°|lm|lx|Bq|Gy|Sv|kat|m|kg|s|A|K|mol|cd|rad|sr|Hz|N|Pa|J|W|C|V|F|Ω|S|Wb|T|H)'
si_prefix = ur'(Y|Z|E|P|T|G|M|k|h|da|d|c|m|µ|n|p|f|a|z|y)'

# roman numeral best guess. will not match I or i as it will overmatch with normal text.
roman_numeral = ur'([VXLCDMvxlcdm][IVXLCDMivxlcdm]{1,}|[IVXLCDMivxlcdm]{2,})'

# regex patterns based on text patterns (i.e. not POS tagged text) to identify tokens that should have a special POS tag
# note: these regex are applied first to the untokenized text (e.g. 'blah blah abc blah') then later to the tokenized patterns (e.g. 'abc'). as such pattern should not expect a space at start.
# note: look ahead and behind to avoid '__' (token replacement characters) and [A-Za-z0-9\-] (matches embedded within another valid token)
#

look_behind_tag = ur'\A.*?(?<!__)(?<![A-Za-z0-9\-])'
look_behind_tag_replacement_only = ur'\A.*?(?<!__)'
look_ahead_tag = ur'(?!__)(?![A-Za-z0-9\-])'
look_ahead_tag_replacement_only = ur'(?!__)'

listTagPatternOrder = [ 'DOUBLE_QUOTED', 'SINGLE_QUOTED', 'PARENTHETICAL_MATERIAL', 'APPOS_ENDING', 'DATE1', 'DATE2', 'DATE3', 'DATE4', 'TIME', 'NUMBER_PATTERN', 'SEMI_COLON', 'AMPERSAND_PHRASE', 'INITIAL', 'TITLE', 'ALPHA_ID', 'PREP_OF' ]
#listTagPatternOrder = [ 'DOUBLE_QUOTED', 'SINGLE_QUOTED', 'PARENTHETICAL_MATERIAL', 'APPOS_ENDING', 'DATE1', 'DATE2', 'DATE3', 'DATE4', 'TIME', 'UNIT1', 'UNIT2', 'NUMBER_PATTERN', 'SEMI_COLON', 'AMPERSAND_PHRASE', 'INITIAL', 'TITLE', 'ALPHA_ID', 'PREP_OF' ]
# PAPER DISCUSSION POINT - assigning POS tagging to avoid problems in dep parse later
dictTagPatterns = {

	# label semi-colon separately from / or : as it tends to be used to separate main clauses
	'SEMI_COLON' : (
		re.compile( look_behind_tag_replacement_only + ur'(?P<SEMI_COLON>;)' + look_ahead_tag_replacement_only, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'SEMI_COLON' ),

	# label preposition 'of' specially so we treat is specially when combining objects later
	# note: check of is not prefixed by _ otherwise we will match the replacement token PREP_OF !
	'PREP_OF' : (
		re.compile( look_behind_tag + ur'(?!_)(?P<PREP_OF>of)' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'PREP_OF' ),

	# common tokens that tend to get broken up under TreebankWordTokenizer
	# note: check of is not prefixed by ' otherwise 1980's. might match
	'INITIAL' : (
		re.compile( look_behind_tag + ur'(?!\')(?P<INITIAL>' + initials + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'INITIAL' ),
	'TITLE' : (
		re.compile( look_behind_tag + ur'(?P<TITLE>(prof\.|prof|dr\.|dr|miss\.|miss|mrs\.|mrs|mr\.|mr))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'TITLE' ),
	'ALPHA_ID' : (
		re.compile( look_behind_tag + ur'(?<!no |p\. )(?<!sce |abv |cva |pl\. |no\. |nos )(?<!limc |sce, |abv, |cva, |nos\. |note |fig\. |figs |fig\. )(?<!limc, |table )(?<!figure |tables )(?<!section |figures )(?P<ALPHA_ID>' + alpha_numeric + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'ALPHA_ID' ),
	
	# common datetime patterns so they are not split up in POS tagging
	# date
	#   YYYY-MM-DD
	#   DD-MM-YY
	#   DD-MM-YYYY
	#   day_name, DD(st|nd|th), month_name, YYYY
	#   month_name, DD(st|nd|th), YYYY
	# time
	#   hh:mm:ss+hh:ss
	#   hh:mm:ss PM|AM
	# 
	# note: day and month can be switched based on locale
	# note: T can connect date and time for ISO formatted datetime
	# note: / or . can replace - for date seperator
	'DATE1' : (
		re.compile( look_behind_tag + ur'(?P<DATE1>([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{2}|[0-9]{4}-[0-9]{2}-[0-9]{4}))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DATE1' ),
	'DATE2' : (
		re.compile( look_behind_tag + ur'(?P<DATE2>([0-9]{4}/[0-9]{2}/[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{2}|[0-9]{4}/[0-9]{2}/[0-9]{4}))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DATE2' ),
	'DATE3' : (
		re.compile( look_behind_tag + ur'(?P<DATE3>([0-9]{4}\.[0-9]{2}\.[0-9]{2}|[0-9]{2}\.[0-9]{2}\.[0-9]{2}|[0-9]{4}\.[0-9]{2}\.[0-9]{4}))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DATE3' ),
	'DATE4' : (
		re.compile( look_behind_tag + ur'(?P<DATE4>(' + days + ur'(,|, | )){0,1}([0-9]{2}(st|nd|rd|th){0,1}(,|, | )' + months + ur'(,|, | )[0-9]{4}|' + months + ur'(,|, | )[0-9]{2}(st|nd|rd|th){0,1}(,|, | )[0-9]{4}))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DATE4' ),
	'TIME' : (
		re.compile( look_behind_tag + ur'(?P<TIME>[0-1]{2}\:[0-1]{2}\:[0-1]{2}( am| pm){0,1}(\+[0-9]{2}\:[0-9]{2}| gmt\+[0-9]{1,2}){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'TIME' ),

	# common units
	#'UNIT1' : (
	#	re.compile( look_behind_tag_replacement_only + ur'(?<=[0-9] )(?P<UNIT1>(' + si_prefix + ur'){0,1}' + si_unit + ur')' + look_ahead_tag, re.UNICODE | re.DOTALL ),
	#	'UNIT1' ),
	#'UNIT2' : (
	#	re.compile( look_behind_tag_replacement_only + ur'(?<=[0-9] )(?P<UNIT2>(' + si_prefix + ur'){0,1}' + si_unit + ur'(\/(' + si_prefix + ur'){0,1}' + si_unit + ur'){0,1})' + look_ahead_tag, re.UNICODE | re.DOTALL ),
	#	'UNIT2' ),

	# POS pattern to capture bad tokenization from datasets such as "can n't"
	'APPOS_ENDING' : (
		re.compile( look_behind_tag + ur'(?P<APPOS_ENDING>(n\'t|\'ve|\'re|\'ie|\'ll|\'an))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'APPOS_ENDING' ),

	# european number patterns e.g. USA '1,000,000.00' FR '1 000 000,00'
	# ratios with numbers e.g. '3/8' '2:1' '2-1'
	# do not ignore case otherwise it will match the replacement tokens themselves (e.g. __TITLE1__ wil match E1 ifignorecase is enabled)
	'NUMBER_PATTERN' : (
		re.compile( look_behind_tag + ur'(?P<NUMBER_PATTERN>([$£e€]|[$£e€] ){0,1}([0-9]+[,.][0-9,.]*[0-9]+|[0-9]+[ ,][0-9 ,]*[0-9]+)|[0-9]+[:/\-][0-9]+)(?![.,/:\-])' + look_ahead_tag, re.UNICODE | re.DOTALL ),
		'NUMBER_PATTERN' ),

	# matching parentheses to indicate parenthetical material. allows (blah) to be treated as a noun. e.g. united states of america (USA), attended next meeting (10:00 October 2nd), cost loads (£10.00)
	# the dep graph will take this entire parenthetical material as a single noun entry, so it does not get in the way of the logical sentence flow
	# note: this can be disabled if we have less formal text where () are used for emoji and likely to be mis-used or not closed properly.
	# note: prevents '_' character to avoid '__' (token replacement characters) being captured erroneous
	'PARENTHETICAL_MATERIAL' : (
		re.compile( look_behind_tag + ur'(?P<PARENTHETICAL_MATERIAL>\([^)_]+\))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'PARENTHETICAL_MATERIAL' ),

	# matching quotes to indicate quoted material. allows "blah" to be treated as a noun. e.g. "originals only" was his mantra
	# note: this can be disabled if we have less formal text where quotes are not always closed properly.
	# note: prevents '_' character to avoid '__' (token replacement characters) being captured erroneous
	'SINGLE_QUOTED' : (
		re.compile( look_behind_tag + ur'(?P<SINGLE_QUOTED>\'[^)_]+\')' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'SINGLE_QUOTED' ),
	'DOUBLE_QUOTED' : (
		re.compile( look_behind_tag + ur'(?P<DOUBLE_QUOTED>(\"|\`\`)[^)_]+(\"|\`\`))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'DOUBLE_QUOTED' ),

	# Ampersand connecting two words (alpha only) usually indicates a noun, not a coordinating conjunction. match 'fox & sons' but not 'fox&some' which would become a single token anyway
	# note: this can be disabled if we have less formal text where quotes are not always closed properly.
	# note: prevents '_' character to avoid '__' (token replacement characters) being captured erroneous
	'AMPERSAND_PHRASE' : (
		re.compile( look_behind_tag + ur'(?P<AMPERSAND_PHRASE>[A-Za-z\-]+ \& [A-Za-z\-]+)' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'AMPERSAND_PHRASE' ),

	# very basic email pattern for ClauseIE datasets
	# note: turn off if URI's expected as it will false match
	'EMAIL_ADDR' : (
		re.compile( look_behind_tag + ur'(?P<EMAIL>E-mail \: [A-Za-z0-9\-]+\.(com|uk|org))' + look_ahead_tag, re.UNICODE | re.DOTALL | re.IGNORECASE ),
		'EMAIL' ),

}

dictTagDependancyParseMapping = {
	'SEMI_COLON' : ':',
	'PREP_OF' : 'IN',
	'NUMBER_PATTERN' : 'CD',
	'DATE1' : 'CD',
	'DATE2' : 'CD',
	'DATE3' : 'CD',
	'DATE4' : 'CD',
	'TIME' : 'CD',
	#'UNIT1' : 'CD',
	#'UNIT2' : 'CD',
	'INITIAL' : 'SYM',
	'TITLE' : 'SYM',
	'APPOS_ENDING' : 'RB',
	'EMAIL' : '#',
	'NAMESPACE' : '#',
	'URI' : '#',
	'ALPHA_ID' : 'NN',
	'PARENTHETICAL_MATERIAL' : 'NN',
	'SINGLE_QUOTED' : 'NN',
	'DOUBLE_QUOTED' : 'NN',
	'AMPERSAND_PHRASE' : 'NN',
}

#
# ** propositional patterns **
# POS patterns to generate seed tuples prior to graph walk and template creation
# {arg} {rel} {arg}
# {rel} = V | VP | VW*P
# V = verb + optional particle (base, past, present) + optional adverb
# P = preposition, particle, inf. marker
# W = noun, adjective, adverb, pronoun, determiner
# {arg} = proper noun phrase (more reliable than noun or proper noun patterns)
# {prep} and then {rel} are matched first to avoid {arg} where then noun is in fact part of a relation (e.g. made a deal with -> deal is a noun)
# Pronoun include personal pronouns (PRP, PRP$) = 1, me, you, possessive pronouns (PP$) = her, ours and relative pronouns (WDT, WP, WP$) = who, which, that, whose, whom
# ReVerb takes longest match (so should be greedy) and merges adjacent sequences of argument and relations
# CITE: Anthony Fader, Stephen Soderland, and Oren Etzioni. 2011. Identifying relations for open information extraction. In Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP '11). Association for Computational Linguistics, Stroudsburg, PA, USA, 1535-1545
# ** ReVerb
# - S R O
# - R = [adj/adv] V
#       R prep
#       R [N/pro/det] prep
# ** ReNoun
# - the A of S, O
# - the A of S is O
# - O,S A
# - O, S's A
# - O, [the] A of S
# - S A O
# - S A, O
# - S's A, O
# ** ClauseIE (S = subject, O = object, V = verb of different types, A = adverb, C = complement)
# - S Vi
# - S Ve A
# - S Vc C
# - S Vmt O
# - S Vdt O O
# - S Vct O A
# - S Vct O C
#
# Seed tuple patterns to used when creating open extraction template patterns. Tuples checked in the strict order they appear here, so put most specific patterns first, and will be executed until there are no more matches.
# Pattern checker get_seed_tuples_from_extractions() allows sequential matches of same type
# e.g. ARGUMENT RELATION RELATION ARGUMENT will match a sequence ARGUMENT RELATION ARGUMENT
# Argument and Pronoun are separated so we can make sure pronouns are not chained (which usually spans gramatical structures and is incorrect)
# Seed tuples chosen based on an analysis of POS patterns associated with entity description text sentences (CH and DBpedia)
#
# These POS tags are mapped tp PENN POS tags, so Stanford Parser can understand them
# note: the lexical tokens are stripped and replaced with spaces to allow nested structures to work for regex. this means only POS tags can be matched.
#
# PAPER DISCUSSION POINT - moving well beyond reVerb POS patterns

listPropExecutionOrder = [ 'CLAUSE_BREAK', 'PREPOSITION', 'PRONOUN', 'RELATION', 'NUMERIC', 'ARGUMENT', 'COORDINATION' ]

dictPropPatterns = {

	'PREPOSITION' : [
		# adjective/adverb P [if not preceeded by a verb]
		re.compile( ur'\A.*?(\(S |\([^V][^)]*\) )(?P<PREPOSITION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}\((TO|IN|PREP_OF) [^)]*\)( \((TO|IN|PREP_OF) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# P adjective/adverb [if not followed by a verb]
		re.compile( ur'\A.*?(?P<PREPOSITION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}\((TO|IN|PREP_OF) [^)]*\)( \((TO|IN|PREP_OF) [^)]*\)){0,19})(?! \(V)', re.UNICODE | re.DOTALL ),

		# P e.g. in
		re.compile( ur'\A.*?(?P<PREPOSITION>\((TO|IN|PREP_OF) [^)]*\)( \((TO|IN|PREP_OF) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

	'RELATION' : [
		# model verb phrase (and associated adjective, adverb or noun)
		re.compile( ur'\A.*?(?P<RELATION>\((MD) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS) [^)]*\)){0,19}( \((NNP|NNPS|NN|NNS) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),

		# adjective/adverb V [if not preceeded by a determiner] e.g. just finished
		re.compile( ur'\A.*?(\(S |\([^D][^)]*\) )(?P<RELATION>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){1,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# V adjective/adverb [if not followed by a verb] [if not preceeded by a determiner] e.g. allow 'seemed not' e.g. avoid 'the netting'
		re.compile( ur'\A.*?(\(S |\([^D][^)]*\) )(?P<RELATION>\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,19}( \((RB|RBR|RP|JJ|JJR|JJS|APPOS_ENDING) [^)]*\)){1,20})(?! \(V)', re.UNICODE | re.DOTALL ),

		# V [if not preceeded by a determiner] e.g. running
		re.compile( ur'\A.*?(\(S |\([^D][^)]*\) )(?P<RELATION>\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# N P [if preceeded by a pronoun] -> single noun (not proper noun) immediately after a pronoun, acting as a verb e.g. <they> plan to
		# PAPER DISCUSSION POINT - use of POS context to infer a verb phrase from a noun and preposition combination
		re.compile( ur'\A.*?\(PRONOUN [ ]*\) (?P<RELATION>\((NN|NNS) [^)]*\) \(PREPOSITION [ ]*\))', re.UNICODE | re.DOTALL ),

		# relation prep e.g. eased up on
		re.compile( ur'\A.*?(?P<RELATION>\(RELATION [ ]*\) \(PREPOSITION [ ]*\))', re.UNICODE | re.DOTALL ),

		# prep relation [if preceeded by a relation] e.g. [believed] to be
		re.compile( ur'\A.*?\(RELATION [ ]*\) (?P<RELATION>\(PREPOSITION [ ]*\) \(RELATION [ ]*\))', re.UNICODE | re.DOTALL ),

		# N adjective [if not followed by a verb] [if not preceeded by a determiner] e.g. 'looks good'
		# removed as too many false positives
		#re.compile( ur'\A.*?(\(S |\([^D][^)]*\) )(?P<RELATION>\((NNP|NNPS|NN|NNS) [^)]*\)( \((NNP|NNPS|NN|NNS) [^)]*\)){0,19}( \((JJ|JJR|JJS) [^)]*\)){1,20})(?! \(V)', re.UNICODE | re.DOTALL ),

		# N APPOS_ENDING [if not preceeded by a determiner] e.g. can n't
		re.compile( ur'\A.*?(\(S |\([^D][^)]*\) )(?P<RELATION>\((NNP|NNPS|NN|NNS) [^)]*\) \(APPOS_ENDING [^)]*\))', re.UNICODE | re.DOTALL ),

		# merge chains of relation into a single relation seed (check last to allow other regex to be tried first)
		re.compile( ur'\A.*?(?P<RELATION>\(RELATION [ ]*\) \(RELATION [ ]*\))', re.UNICODE | re.DOTALL ),

		],

	'ARGUMENT' : [
		# pronoun
		re.compile( ur'\A.*?(?P<ARGUMENT>\(PRONOUN [ ]*\))', re.UNICODE | re.DOTALL ),

		# date, time or datetime phrase
		re.compile( ur'\A.*?(?P<ARGUMENT>(\(TIME [ ]*\)|\((DATE1|DATE2|DATE3|DATE4) [ ]*\)([ T]\(TIME [ ]*\)){0,1}))', re.UNICODE | re.DOTALL ),

		# numeric phrase
		re.compile( ur'\A.*?(?P<ARGUMENT>\(NUMERIC [ ]*\)( \(PREPOSITION [ ]*\)){0,1}( \((NNP|NNPS|NN|NNS|ALPHA_ID) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),

		# noun phrase (including :-/ e.g. red/blue)
		re.compile( ur'\A.*?(?P<ARGUMENT>(\(DT [^)]*\) ){0,20}(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((NNP|NNPS|NN|NNS|ALPHA_ID|INITIAL|TITLE|AMPERSAND_PHRASE) [^)]*\))( \((NNP|NNPS|NN|NNS|ALPHA_ID|POS|INITIAL|\:|AMPERSAND_PHRASE) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# parenthetical phrase or quoted phrase acting as an argument in itself e.g. '(NYC)' or '(the best company)' or 'John said "i went to the beach"'
		re.compile( ur'\A.*?(?P<ARGUMENT>\((SINGLE_QUOTED|DOUBLE_QUOTED|PARENTHETICAL_MATERIAL) [^)]*\))', re.UNICODE | re.DOTALL ),

		# allow an verb/adjective/adverb preceeded by a determiner to act as an argument e.g. the best
		# PAPER DISCUSSION POINT - use of POS context to infer a noun phrase from a det verb pattern
		re.compile( ur'\A.*?(?P<ARGUMENT>(\(DT [^)]*\) ){1,20}\((RB|RBR|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ|POS) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# prep argument -> merge prep arg
		re.compile( ur'\A.*?(?P<ARGUMENT>\(PREPOSITION [ ]*\) \(ARGUMENT [ ]*\))', re.UNICODE | re.DOTALL ),

		# argument prep -> merge arg prep
		re.compile( ur'\A.*?(?P<ARGUMENT>\(ARGUMENT [ ]*\) \(PREPOSITION [ ]*\))', re.UNICODE | re.DOTALL ),

		# merge chains of arguments into a single argument seed (check last to allow other regex to be tried first)
		re.compile( ur'\A.*?(?P<ARGUMENT>\(ARGUMENT [ ]*\) \(ARGUMENT [ ]*\))', re.UNICODE | re.DOTALL ),

		],

	'NUMERIC' : [
		# currency $ 50.12
		# numeric value: e.g. approx 10 dead, 10's dead
		# fractions 3/8, ratios 2:1
		# date 11 a.m.
		re.compile( ur'\A.*?(?P<NUMERIC>(\((RB|RBR|RBS|[#]|[$]) [^)]*\) ){0,20}\((CD|NUMBER_PATTERN) [^)]*\)( \(\: [^)]*\) \((CD|NUMBER_PATTERN) [^)]*\)){0,1}( \((JJ|JJR|JJS|POS|INITIAL|UNIT) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),

		# merge chains of numeric
		re.compile( ur'\A.*?(?P<NUMERIC>\(NUMERIC [ ]*\) \(NUMERIC [ ]*\))', re.UNICODE | re.DOTALL ),

		],

	'PRONOUN' : [
		# pronoun -> allow adjective and possessive ending (e.g. 's)
		re.compile( ur'\A.*?(?P<PRONOUN>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\))( \((PRP|PRP[$]|WP|WP[$]|WDT|POS|APPOS_ENDING) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

	# explicit punctuation is used to break up potential clauses, that would otherwise get merged (we dont want seeds that span relative clauses)
	'CLAUSE_BREAK' : [
		# semi-colon - separating two main clauses
		# PAPER DISCUSSION POINT - using punctuation and coordination to break up seed terms (so we avoid variables that erroneously span clauses)
		re.compile( ur'\A.*?(?P<CLAUSE_BREAK>\(SEMI_COLON [^)]*\))', re.UNICODE | re.DOTALL ),

		# comma followed by a pronoun, verb or model verb - marking non-defining clauses
		re.compile( ur'\A.*?(?P<CLAUSE_BREAK>\(\, [^)]*\)) \((PRP|PRP[$]|WP|WP[$]|WDT|VB|VBD|VBG|VBN|VBP|VBZ|MD) [^)]*\)', re.UNICODE | re.DOTALL ),
		],

	# coordinating conjunctions including comma separated lists of nouns (so we break up argument chains)
	'COORDINATION' : [
		# comma followed by CC
		re.compile( ur'\A.*?(?P<COORDINATION>\(\, [^)]*\)( \(CC [^)]*\)){1,20})', re.UNICODE | re.DOTALL ),

		# comma followed by argument (noun phrase)
		re.compile( ur'\A.*?(?P<COORDINATION>\(\, [^)]*\)) \(ARGUMENT [ ]*\)', re.UNICODE | re.DOTALL ),

		# CC
		re.compile( ur'\A.*?(?P<COORDINATION>\(CC [^)]*\)( \(CC [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

}

#
# contiguous_triples -> look for {arg,relxN,arg}
#
listSeedTuplesProp = [
	( 'ARGUMENT', 'RELATION', 'ARGUMENT' ),
]
listPropPreventSequentialMatchesTriples = [
	'ARGUMENT',
]


# for each var type, phrase POS patterns to use to get phrases to lookup in lexicon (for var candidates)
dictPropVarPhrasePatterns ={
	'ARGUMENT' : ['noun_phrase','pronoun'],
	'RELATION' : ['verb_phrase', 'noun_phrase'],
	'CLAUSE_BREAK' : [],
	'PREPOSITION' : [],
	'PRONOUN' : [],
	'NUMERIC' : [],
	'COORDINATION' : []
	}

# seed to template variable mapping (names must not have _ in them)
dictPropSeedToTemplateMapping = {
	'RELATION' : 'rel',
	'ARGUMENT' : 'arg',
}

# dep types to not navigate during graph walk to generate templates
setAvoidDepInWalkProp = set([])

# template aggressive generalization strategy
# default = use lex for context = relex LEX constraints for arg/rel, and relax POS constraints for ctxt
dictGeneralizeStrategyProp = {
	'relax_lex' : ['arg','rel'],
	'relax_pos' : [],
	'relax_pos_number_aware' : ['ctxt']
}
# default = use pos for context = relex LEX constraints for arg/rel/ctxt
'''
dictGeneralizeStrategyProp = {
	'relax_lex' : ['arg','rel','ctxt'],
	'relax_pos' : [],
	'relax_pos_number_aware' : []
}
'''

# variable patterns that will form propositional structures (typically 3 or 4 gram tuples)
# list of ( pattern, index_target, type_target )
# target is *rel*, choose extraction which has the minimize semantic drift for each target
listPropositionPatternPropSet = [
	( [ 'arg', 'rel', 'arg' ], 1, 'rel' ),
]

dictDisplacedContextProp = openiepy.comp_sem_lib.dict_displaced_context_default
dictPropStoplistPrefixProp = openiepy.comp_sem_lib.dict_index_stoplist_prefix_default
dictPropStoplistSuffixProp = openiepy.comp_sem_lib.dict_index_stoplist_suffix_default

# inter-var semantic drift thresholds
# max drift = max inter-var semantic drift allowed when filtering generated extractions
# max end to end drift = max allowed variable semantic drift from first to last var, when generating propositions from extractions
nMaxSemanticDriftProp = None
nMaxEndToEndSemanticDriftProp = None
dictSemanticDriftProp = openiepy.comp_sem_lib.dict_semantic_drift_default


#
# ** attributional patterns **
# attributional propositions asset S is/has A O
# S = subject
# A = attribute (attr, attr_base + attr_prep)
# O = object
# DISCUSSION POINT > OpenIE systems currently focus on propositional structures. ReNoun has looked at SAO patterns. AttribIE 
# ** AttribIE patterns
# - S A P O
# - S P O
# - S A O
# - S A <end>
# - <start> A P O
# - <start> P O
# - <start> A O
# - <start> A <end>

#
# Seed tuple patterns to used when creating open extraction template patterns. Tuples checked in the strict order they appear here, so put most specific patterns first.
# Pattern checker get_seed_tuples_from_extractions() allows sequential matches of same type
# e.g. ARGUMENT RELATION RELATION ARGUMENT will match a sequence ARGUMENT RELATION ARGUMENT
# Argument and Pronoun are separated so we can make sure pronouns are not chained (which usually spans gramatical structures and is incorrect)
# Seed tuples chosen based on an analysis of POS patterns associated with entity description text sentences (CH and DBpedia)
#
# These POS tags are mapped tp PENN POS tags, so Stanford Parser can understand them
#

listAttrExecutionOrder = [ 'PRONOUN', 'NUMERIC', 'OBJECT', 'SUBJECT', 'ATTR', 'ATTR_BASE', 'ATTR_PREP', 'ATTR_NO_OBJ_NO_SUBJ', 'ATTR_NO_OBJ' ]

dictAttrPatterns = {

	'OBJECT' : [
		# PAPER DISCUSSION POINT - use of POS context to infer better noun phrases

		# date, time or datetime phrase
		re.compile( ur'\A.*?(?P<OBJECT>(\(TIME [ ]*\)|\((DATE1|DATE2|DATE3|DATE4) [ ]*\)([ T]\(TIME [ ]*\)){0,1}))', re.UNICODE | re.DOTALL ),

		# adj <comma> adj verb(base form, past tense, past participle) prexifing a noun phrase e.g. short, sharp everted rim
		re.compile( ur'\A.*?(?P<OBJECT>(\((RB|RBR|JJ|JJR|JJS) [^)]*\) ){1,20}\(\, [^)]*\) (\((RB|RBR|JJ|JJR|JJS) [^)]*\) ){1,20}(\((VB|VBD|VBN) [^)]*\) ){1,20}\((NNP|NNPS|NN|NNS) [^)]*\)( \((NNP|NNPS|NN|NNS|POS|PARENTHETICAL_MATERIAL) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# [adjective/adverb] verb(base form, past tense, past participle) [adjective/adverb] noun phrase e.g. handle zone
		re.compile( ur'\A.*?(?P<OBJECT>(\((RB|RBR|JJ|JJR|JJS) [^)]*\) ){0,20}(\((VB|VBD|VBN) [^)]*\) ){1,20}(\((RB|RBR|JJ|JJR|JJS) [^)]*\) ){0,20}\((NNP|NNPS|NN|NNS) [^)]*\)( \((NNP|NNPS|NN|NNS|POS|PARENTHETICAL_MATERIAL) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# DT [adjective/adverb] V [adjective/adverb] e.g. the best
		re.compile( ur'\A.*?(?P<OBJECT>(\(DT [^)]*\) ){1,20}\((RB|RBR|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ|POS|PARENTHETICAL_MATERIAL) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# P [adjective/adverb] V [adjective/adverb] e.g. of marching hoplites
		re.compile( ur'\A.*?\((TO|IN|PREP_OF) [^)]*\) (?P<OBJECT>(\((RB|RBR|JJ|JJR|JJS) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ|POS|PARENTHETICAL_MATERIAL) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# [adjective/adverb] noun phrase (NOT including :-/ so we can break apart attributes e.g. red/blue)
		re.compile( ur'\A.*?(?P<OBJECT>(\(DT [^)]*\) ){0,20}(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((NNP|NNPS|NN|NNS|ALPHA_ID|INITIAL|TITLE|AMPERSAND_PHRASE) [^)]*\))( \((NNP|NNPS|NN|NNS|ALPHA_ID|POS|INITIAL|AMPERSAND_PHRASE|PARENTHETICAL_MATERIAL) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),

		# numeric prefix to O e.g. 20 dead
		# CD [P] O
		re.compile( ur'\A.*?(?P<OBJECT>\(NUMERIC [ ]*\)( \((TO|IN|PREP_OF) [^)]*\)){0,20} \(OBJECT [ ]*\))', re.UNICODE | re.DOTALL ),

		# O P numeric e.g. size of 12.45
		# O P CD
		re.compile( ur'\A.*?(?P<OBJECT>\(OBJECT [ ]*\)( \((TO|IN|PREP_OF) [^)]*\)){0,20} \(NUMERIC [ ]*\))', re.UNICODE | re.DOTALL ),

		# numeric acting as an O on its own e.g. population was 563
		# O [adjective/adverb] V [adjective/adverb] CD
		re.compile( ur'\A.*?\(OBJECT [ ]*\) \((RB|RBR|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((RB|RBR|RP|JJ|JJR|JJS|VB|VBD|VBG|VBN|VBP|VBZ|POS|PARENTHETICAL_MATERIAL) [^)]*\)){0,19} (?P<OBJECT>\(NUMERIC [ ]*\))', re.UNICODE | re.DOTALL ),

		# merge O coordinations as they are really just a subject
		# O , O , O , CC [adjective/adverb] O
		re.compile( ur'\A.*?(?P<OBJECT>\(OBJECT [ ]*\)( \(, [^)]*\) \(OBJECT [ ]*\)){0,20}( \(, [^)]*\)){0,1} \(CC [^)]*\)( \((RB|RBR|JJ|JJR|JJS) [^)]*\)){0,1} \(OBJECT [ ]*\))', re.UNICODE | re.DOTALL ),

		# merge sequential entries (O O) as they are really just a object
		re.compile( ur'\A.*?(?P<OBJECT>\(OBJECT [ ]*\) \(OBJECT [ ]*\))', re.UNICODE | re.DOTALL ),

		# merge sequential (O P(of) O) -> P O to force sequences of 'A of B of C' to be matched as a whole as they cannot be applied to subject as fragments with good meaning.
		# other 100 preposition types (e.g. in, with ...) can normally stand alone with the original subject
		# PAPER DISCUSSION POINT - use of permissive O P O merging to aggregate attributes (high P, less attributes), or selective O P O merging (lower P, more attributes)
		# [any] O P O [any]
		re.compile( ur'\A.*?(?P<OBJECT>\(OBJECT [ ]*\) \(PREP_OF [ ]*\) \(OBJECT [ ]*\))', re.UNICODE | re.DOTALL ),
		# [not start] O P O [not end]
		#re.compile( ur'\A.*?(?<!\(S )(?<! (\:|\.)\))(?<! SEMI_COLON\))(?P<OBJECT>\(OBJECT [ ]*\) \(PREP_OF [^)]*\) \(OBJECT [ ]*\))(?!\)\Z)(?! \((\:|\.))(?! \(SEMI_COLON)', re.UNICODE | re.DOTALL ),
		# [start] O P O [not end]
		#re.compile( ur'\A\(S (?P<OBJECT>\(OBJECT [ ]*\) \(PREP_OF [^)]*\) \(OBJECT [ ]*\))(?!\)\Z)(?! \((\:|\.))(?! \(SEMI_COLON)', re.UNICODE | re.DOTALL ),
		# [not start] O P O [end]
		#re.compile( ur'\A.*?(?<!\(S )(?<! (\:|\.)\))(?<! SEMI_COLON\))(?P<OBJECT>\(OBJECT [ ]*\) \(PREP_OF [^)]*\) \(OBJECT [ ]*\))(\)\Z| \((\:|\.)| \(SEMI_COLON)', re.UNICODE | re.DOTALL ),

		],

	'SUBJECT' : [
		# <start> ==  \A(S , ; :
		# PAPER DISCUSSION POINT - use of POS context to infer better noun phrases

		# pronoun or Existential There - do not allow it to be merged in a coordination as its almost always a subject on its own
		# e.g. stallion rearing to right COORD(,) PRO(its) forelegs off the ground
		re.compile( ur'\A.*?(?P<SUBJECT>\((PRONOUN|EX) [ ]*\))', re.UNICODE | re.DOTALL ),

		# promote O to S if its prefixed by <start>
		re.compile( ur'\A(\(S |.*?\((,|\:|\.|SEMI_COLON) [^)]*\) )(?P<SUBJECT>\(OBJECT [ ]*\))', re.UNICODE | re.DOTALL ),

		# merge sequential entries (S S) (S O) as they are really just a subject
		re.compile( ur'\A.*?(?P<SUBJECT>\(SUBJECT [ ]*\) \((SUBJECT|OBJECT) [ ]*\))', re.UNICODE | re.DOTALL ),

		],

	'ATTR' : [
		# [adjective/adverb] V[any] [adjective/adverb] [DT] O
		re.compile( ur'\A.*?(?P<ATTR>(\((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,20}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \(DT [^)]*\)){0,20}) \(OBJECT [ ]*\)', re.UNICODE | re.DOTALL ),

		# note: do not merge chains of attributes, as we want them all individually
		],

	'ATTR_BASE' : [
		# [adjective/adverb] V[any] ==> suffix by [adjective/adverb] P [adjective/adverb] [V any] [adjective/adverb] [DT] O
		re.compile( ur'\A.*?(?P<ATTR_BASE>(\((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,20})( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20} \((TO|IN|PREP_OF) [ ]*\)( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\) ){0,20}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \(DT [^)]*\)){0,20} \(OBJECT [ ]*\)', re.UNICODE | re.DOTALL ),

		# note: do not merge chains of attributes, as we want them all individually
		],

	'ATTR_PREP' : [
		# [adjective/adverb] P [adjective/adverb] [V any] [adjective/adverb] [DT] O
		re.compile( ur'\A.*?(?P<ATTR_PREP>(\((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\) ){0,20}\((TO|IN|PREP_OF) [ ]*\)( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \((VB|VBD|VBG|VBN|VBP|VBZ) [^)]*\)){0,20}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \(DT [^)]*\)){0,20}) \(OBJECT [ ]*\)', re.UNICODE | re.DOTALL ),

		# note: do not merge chains of attributes, as we want them all individually
		],

	'ATTR_NO_OBJ' : [
		# <end> == look )\Z , . ; :

		# [adjective/adverb] V|P [adjective/adverb] [P] [adjective/adverb] <end>
		re.compile( ur'\A.*?(?P<ATTR_NO_OBJ>(\((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ|TO|IN|PREP_OF) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ|TO|IN|PREP_OF) [^)]*\)){0,20}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \((TO|IN|PREP_OF) [ ]*\)){0,1}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20})(\)\Z| \((,|\:|\.|SEMI_COLON) [^)]*\))', re.UNICODE | re.DOTALL ),

		],

	'ATTR_NO_OBJ_NO_SUBJ' : [
		# <end> == look )\Z , . ; :

		# [adjective/adverb] V|P [adjective/adverb] [P] [adjective/adverb] <end>
		re.compile( ur'\A\(S (?P<ATTR_NO_OBJ_NO_SUBJ>(\((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\) ){0,20}\((VB|VBD|VBG|VBN|VBP|VBZ|TO|IN|PREP_OF) [^)]*\)( \((VB|VBD|VBG|VBN|VBP|VBZ|TO|IN|PREP_OF) [^)]*\)){0,20}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20}( \((TO|IN|PREP_OF) [ ]*\)){0,1}( \((RB|RBR|RP|JJ|JJR|JJS|PARENTHETICAL_MATERIAL) [^)]*\)){0,20})(\)\Z| \((,|\:|\.|SEMI_COLON) [^)]*\))', re.UNICODE | re.DOTALL ),

		],

	'NUMERIC' : [
		# currency $ 50.12
		# numeric value: e.g. approx 10 dead, 10's dead
		# fractions 3/8, ratios 2:1
		# date 11 a.m.
		re.compile( ur'\A.*?(?P<NUMERIC>(\((RB|RBR|RBS|[#]|[$]) [^)]*\) ){0,20}\((CD|NUMBER_PATTERN) [^)]*\)( \(\: [^)]*\) \((CD|NUMBER_PATTERN) [^)]*\)){0,1}( \((JJ|JJR|JJS|POS|INITIAL) [^)]*\)){0,20})', re.UNICODE | re.DOTALL ),

		# merge chains of numeric
		re.compile( ur'\A.*?(?P<NUMERIC>\(NUMERIC [ ]*\) \(NUMERIC [ ]*\))', re.UNICODE | re.DOTALL ),

		],

	'PRONOUN' : [
		# pronoun -> allow adjective and possessive ending (e.g. 's)
		re.compile( ur'\A.*?(?P<PRONOUN>(\((RB|RBR|RP|JJ|JJR|JJS) [^)]*\) ){0,20}(\((PRP|PRP[$]|WP|WP[$]|WDT) [^)]*\))( \((PRP|PRP[$]|WP|WP[$]|WDT|POS|APPOS_ENDING) [^)]*\)){0,19})', re.UNICODE | re.DOTALL ),
		],

}

#
# contiguous_tuple_with_seq_groups -> look for {arg,relxN,arg}
#
listSeedTuplesAttr = [
	( 'SUBJECT', 'ATTR_BASE', ('ATTR_PREP','OBJECT') ),
	( 'SUBJECT', ('ATTR_PREP','OBJECT'), ),
	( 'SUBJECT', ('ATTR','OBJECT'), ),
	( 'SUBJECT', 'ATTR_NO_OBJ' ),
	( ( 'START', 'ATTR_NO_OBJ_NO_SUBJ', 'END' ), ),
#	( ( 'START', 'ATTR_BASE', 'ATTR_PREP','OBJECT' ), ),
#	( ( 'START', 'ATTR_PREP', 'OBJECT' ), ),
#	( ( 'START', 'ATTR', 'OBJECT' ), ),
	# disable for academic paper, but useful for GRAVITATE labelling
	#( ( 'START', 'SUBJECT', 'END' ), ),
]

listAttrPreventSequentialMatchesTriples = [
	'ATTR', 'ATTR_BASE', 'ATTR_PREP', 'ATTR_NO_OBJ', 'ATTR_NO_OBJ_NO_SUBJ'
]

# for each var type, phrase POS patterns to use to get phrases to lookup in lexicon (for var candidates)
# TODO currently lexicon filtering has not been tested - it might help or make things worse
# TODO REVIEW (add prep_phrase?)
dictAttrVarPhrasePatterns ={
	'SUBJECT' : ['noun_phrase','pronoun'],
	'OBJECT' : ['noun_phrase','pronoun'],
	'ATTR_BASE' : ['verb_phrase', 'noun_phrase'],
	'ATTR_PREP' : [],
	'ATTR' : ['verb_phrase', 'noun_phrase'],
	'ATTR_NO_OBJ' : ['verb_phrase', 'noun_phrase'],
	'ATTR_NO_OBJ_NO_SUBJ' : ['verb_phrase', 'noun_phrase'],
	'PRONOUN' : [],
	'NUMERIC' : [],
	}

# seed to template variable mapping (names must not have _ in them)
dictAttrSeedToTemplateMapping = {
	'SUBJECT' : 'subj',
	'OBJECT' : 'obj',
	'ATTR_BASE' : 'attrbase',
	'ATTR_PREP' : 'attrprep',
	'ATTR' : 'attr',
	'ATTR_NO_OBJ' : 'attrnoobj',
	'ATTR_NO_OBJ_NO_SUBJ' : 'attrnoobjnosubj',
}

# dep types to not navigate during graph walk to generate templates
#setAvoidDepInWalkAttr = set(['dep'])
setAvoidDepInWalkAttr = set([])

# template aggressive generalization strategy
dictGeneralizeStrategyAttr = {
	'relax_lex' : ['subj','obj','attr','attrbase','attrprep','attrnoobj','attrnoobjnosubj'],
	'relax_pos' : [],
	'relax_pos_number_aware' : ['ctxt']
}

# variable patterns that will form propositional structures (typically 3 or 4 gram tuples)
# list of ( pattern, index_target, type_target )
# note: a prop filter strategy of prop_subsumption will avoid patterns like {subj} being perferred to a fuller prop pattern such as {subj, attr, obj}
'''
listPropositionPatternAttrSet = [
	( [ 'subj', 'attrbase', 'attrprep', 'obj' ], 2, 'attrprep' ),
	( [ 'subj', 'attrprep', 'obj' ], 1, 'attrprep' ),
	( [ 'subj', 'attr', 'obj' ], 1, 'attr' ),
	( [ 'subj', 'attrnoobj' ], 1, 'attrnoobj' ),
	( [ 'attrnoobjnosubj', ], 0, 'attrnoobjnosubj' ),
	( [ 'attrbase', 'attrprep', 'obj' ], 1, 'attrprep' ),
	( [ 'attrprep', 'obj' ], 0, 'attrprep' ),
	( [ 'attr', 'obj' ], 0, 'attr' ),
	( [ 'subj', ], 0, 'subj' ),
]
'''

# target is *obj*, choose extraction which has the minimize semantic drift for each target
listPropositionPatternAttrSet = [
	( [ 'subj', 'attrbase', 'attrprep', 'obj' ], 3, 'obj' ),
	( [ 'subj', 'attrprep', 'obj' ], 2, 'obj' ),
	( [ 'subj', 'attr', 'obj' ], 2, 'obj' ),
	( [ 'subj', 'attrnoobj' ], 1, 'attrnoobj' ),
	( [ 'attrnoobjnosubj', ], 0, 'attrnoobjnosubj' ),
#	( [ 'attrbase', 'attrprep', 'obj' ], 2, 'obj' ),
#	( [ 'attrprep', 'obj' ], 1, 'obj' ),
#	( [ 'attr', 'obj' ], 1, 'obj' ),
	# disable for academic paper, but useful for GRAVITATE labelling
	#	( [ 'subj', ], 0, 'subj' ),
]

dictDisplacedContextAttr = {
	'subj' : [],
	'obj' : [],
	'attr' : openiepy.comp_sem_lib.dict_displaced_context_default['rel'],
	'attrbase' : openiepy.comp_sem_lib.dict_displaced_context_default['rel'],
	'attrprep' : openiepy.comp_sem_lib.dict_displaced_context_default['rel'],
	'attrnoobj' : openiepy.comp_sem_lib.dict_displaced_context_default['rel'],
	'attrnoobjnosubj' : openiepy.comp_sem_lib.dict_displaced_context_default['rel'],
}

dictPropStoplistPrefixAttr = None
dictPropStoplistSuffixAttr = None

# inter-var semantic drift thresholds
# max drift = max inter-var semantic drift allowed when filtering generated extractions
# max end to end drift = max allowed variable semantic drift from first to last var, when generating propositions from extractions
nMaxSemanticDriftAttr = 10000
nMaxEndToEndSemanticDriftAttr = None
dictSemanticDriftAttr = {
	# coordination
	'conj' : 100,
	#'cc' : 100,
	# loose joining relations
	#'parataxis' : 20,
	#'list' : 20,
	#'punct' : 20,
	#'dislocated' : 20,
	#'remnant' : 20,
	# unknown dep
	#'dep' : 20,
	# non-core predicate dep
	#'acl:relcl' : 20,
	#'acl' : 20,
	#'advcl' : 20,
	#'nfincl' : 20,
	#'ncmod' : 20,
}

# 
# TODO EVALUATION
# OPTION1 > compare <start> O P O    AND    <any> O P O ==> concatenation of prepositional structures
# OPTION2 > compare nMaxSemanticDriftAttr = 10000    AND    nMaxSemanticDriftAttr = 99 (with conj scoring 100) ==> allow or deny patterns spanning a conjunction
# OPTION3 > compare with and without <start> subj <end> patterm ==> statements of object type
#


#
# Dependency graph navigation restrictions
# Depending on the extracted variable type a different branch navigation path will be chosen to capture relevant dependent text under each branches root node. This captures the contextual text for each extracted variable.
#

# contextual dep's to include under seed head nodes in a graph walk (1 deep child from head node).
# if these match explicitly another variable, they will not be added as context
# this also allows ensures the non-context variables are minimal in length
# context vars can be displaced (left or right) when generating propositional phrases to allow minimal target types (e.g. smallest verb around relation target). its a good idea to get all but essential verb/noun as context therefore.
# - core dependents [rel]
# - preposition, possessive [arg, rel, context]
# - non-core dependents of clausal predicates [rel]
# PAPER DISCUSSION POINT - breaking down branches [especially relation] into context so they can be displaced later to create a minimal relation phrase (but not lost)
dictContextualDepTypes = {
	'rel' : set([
		# for minimal rel set everything as context (for possible displacement)

		# core dependents of clausal predicates
		# except ccomp (which is important for rel meaning - so we collapse it rel later)
		'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','xcomp',

		# non-core dependents of clausal predicates
		'nmod', 'nmod:*', 'advcl', 'advcl:*', 'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		# except cop and auxpass, as this must appear with non-verbal predicate to make a sensible relation
		'vocative', 'discourse', 'expl', 'mark', 'punct',
		# 'cop', 'aux', 'auxpass'

		# noun dependents
		'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		'conj', 'cc',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# other
		# allow dep for relations, not arguments, as it can add important context. add it as context so it can be displaced as needed.
		'dep',

		]),
	'arg' : set([
		# noun dependents
		# TEST2
		'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# non-core dependents of clausal predicates
		'neg',

		]),
	'ctxt' : set([
		# core dependents of clausal predicates
		'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# coordination
		'conj','cc',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# non-core dependents of clausal predicates
		'neg',
		]),
	'subj' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'obj' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'attr' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'attrbase' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'attrprep' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'attrnoobj' : set([
		# no context as will will rely on collapse to make phrases
		]),
	'attrnoobjnosubj' : set([
		# no context as will will rely on collapse to make phrases
		]),
	}




# set of variable types that should be serialized (pretty print and encoding)
# note: any var type missing from this list will be assumed to be context
setGraphDepTypes = set([ 'rel','arg','ctxt','subj','obj','attr','attrbase','attrprep','attrnoobj','attrnoobjnosubj' ])

# graph dependency types to collapse into node branch prety print
# remember all seed pattern nodes are included on path, so this is to capture deep tree context NOT immediate adverb/adjectives
# note: a None entry will allow any dep type to be collapsed and get the whole branch
# note: any var type missing from this list will be assumed to be context
dictCollapseDepTypes = {
	'rel' : set([
		# allow everything except coordination, noun dependents and some non-core dependents and dep
		# core dependents of clausal predicates
		'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','xcomp',
		# 'ccomp' TEST1

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# other
		# avoid dep as it can bring in 'related' tokens e.g. subj from other parts of the sent that really should not be collapsed. doing this can miss the odd title but its best to avoid some really bad errors
		#'dep',

		]),
	'arg' : set([
		# allow everything except appos and dep
		# core dependents of clausal predicates
		'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'nmod', 'nmod:*','advcl', 'advcl:*','neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents (without appos)
		'nummod', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		'conj','cc',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# other
		# dep links some stuff like titles, # ... but it also can link really tenuous deps as its a default connection type from dep parser
		# PAPER DISCUSSION POINT - dep graph failures where 'dep' is used, and if we use them or not. we use them as on average they connect more useful info than erroneous info
		'dep',

		]),
	'ctxt' : set([
		# allow everything for context
		# core dependents of clausal predicates
		'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'nmod', 'nmod:*', 'advcl', 'advcl:*', 'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		'conj','cc',

		# case-marking, prepositions, possessive
		'case', 'case:*',

		# other
		'dep',

		]),
	'subj' : set([

		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		#'nmod', 'nmod:*', 'advcl', 'advcl:*', 'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		#'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',
		# allow nmod collapse, as we allow compound nmod ATTR's
		# 'nmod', 'nmod:*', 'amod'

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'obj' : set([

		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		#'nmod', 'nmod:*', 'advcl', 'advcl:*', 'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		#'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',
		# allow nmod collapse, as we allow compound nmod ATTR's
		# 'nmod', 'nmod:*', 'amod'

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'attr' : set([
		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'attrbase' : set([
		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'attrprep' : set([
		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'attrnoobj' : set([
		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		#'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
	'attrnoobjnosubj' : set([
		# core dependents of clausal predicates
		#'nsubj','nsubjpass','dobj','iobj','csubj','csubjpass','ccomp','xcomp',

		# non-core dependents of clausal predicates
		'neg', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'advmod', 'acl', 'acl:*',

		# special clausal dependents
		'vocative', 'discourse', 'expl', 'aux', 'auxpass', 'cop', 'mark', 'punct',

		# noun dependents
		#'nummod', 'appos', 'nmod', 'nmod:*', 'relcl', 'nfincl', 'nfincl:*', 'ncmod', 'ncmod:*', 'amod', 'advmod', 'det', 'neg',

		# compounding and unanalyzed
		#'compound', 'compound:*', 'name', 'mwe', 'foreign','goeswith',

		# coordination
		#'conj','cc',

		# case-marking, prepositions, possessive
		#'case', 'case:*',

		# other
		#'dep',
		]),
}


