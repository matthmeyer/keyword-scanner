#!/usr/bin/env python
# -*- coding: utf-8 -*-
import spacy
import Levenshtein
import re
import sqlite3
import json

nlp = spacy.load("de_core_news_sm")
label_normadaten = {'PER': 'p', 'LOC': 'g', 'ORG': 'k'}

class meta_kw:
	def __init__(self, dic):
		self.title = dic['title']
		self.word_weights = dic['words']
		self.relevance = 0

	def weight_words(self, all_words_counted):
		word_weights = {}
		for word, treffer in self.words_counted.items():
			try:
				weight = treffer / leipz_words[word]
			except KeyError:
				weight = 1
			if weight > 1:
				weight = 1
			word_weights[word] = weight

		self.word_weights = word_weights

	def check_word(self,word):
		try:
			self.relevance += self.word_weights[word]
		except KeyError:
			pass



class Keyword:
	def __init__(self, title=None, c=None, synonyme=[]):
		self.title = title

		c.execute("SELECT pageid, title, title_norm FROM articles WHERE title = ?", (title,))
		r = c.fetchone()
		self.pageid = r[0]

		synonyme.extend([r[1], r[2]])

		c.execute("""SELECT alias FROM aliases
						LEFT JOIN article_aliases ON aliases.id = article_aliases.alias_pk
						WHERE article_pk = ?""", (self.pageid,))
		synonyme.extend([x[0] for x in c.fetchall()])

		c.execute("""SELECT redirects_from FROM redirects WHERE redirects_to = ?""", (self.pageid,))
		synonyme.extend([x[0] for x in c.fetchall()])
		synonyme = list(set(synonyme))
		syn_new = []
		for syn in synonyme:
			if syn and ' ' not in syn and len(syn) > 1:
				# #print(syn)
				c.execute("""SELECT nom_sg,nom_pl,gen_sg,gen_pl,dat_sg,dat_pl,akk_sg,akk_pl FROM wikt_words WHERE title = ?""", (syn,))
				for row in c.fetchall():
					syn_new.extend([row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[7]])
		synonyme.extend(syn_new)
		self.synonyme = sorted(list(set([x.lower() for x in synonyme if x and len(x) > 1])), key=len, reverse=True)
		self.occurences = 0

	def add_to_occurences(self, to_add):
		self.occurences += to_add



def search_kw_kandidat(ent, c, improved=None):
	kw_kandidat = []

	if not improved:
		improved = ent.text.replace('Dr. ', '')
	print('improved', improved)
	c.execute("SELECT pageid, title, begriff, normdaten, views, norm_syn, alias_syn FROM articles WHERE title_norm = ?", (improved,))
	r = c.fetchall()

	if r:
		for row in r:
			kw_kandidat.append(row)

	c.execute("SELECT articles.pageid, title, begriff, normdaten, views, norm_syn, alias_syn FROM redirects INNER JOIN articles ON articles.pageid = redirects.redirects_to WHERE redirects_from = ?", (improved,))
	r = c.fetchall()

	for row in r:
		kw_kandidat.append(row)


	if kw_kandidat == [] and len(ent.text) > 5:
		improved = improved.replace('-', ' ').replace('\n', ' ')
		while '  ' in improved:
			improved = improved.replace('  ', ' ')

		c.execute("""SELECT pageid, title, begriff, normdaten, views, norm_syn, alias_syn FROM articles 
						WHERE title_norm = ? AND ? >= LENGTH(title)
						AND begriff != 1""", (improved, len(improved) + improved.count(' ') * 2))
		r = c.fetchall()
		r = []
		for row in r:
			if row not in r:
				kw_kandidat.append(row)

	if kw_kandidat == [] and len(ent.text) > 5:
		improved = improved.replace('-', ' ').replace('\n', ' ')
		while '  ' in improved:
			improved = improved.replace('  ', ' ')


		c.execute("""SELECT articles.pageid, title, begriff, normdaten, views, norm_syn, alias_syn FROM redirects
						INNER JOIN articles ON articles.pageid = redirects.redirects_to
						WHERE redirects_from = ? AND ? >= LENGTH(redirects_from)
						AND begriff != 1""", (improved, len(ent.text) + improved.count(' ') * 2))
		result = c.fetchall()
		# Entferne Duplikate
		r = []
		for row in r:
			if row not in r:
				kw_kandidat.append(row)

	return kw_kandidat


def begriffsklaerung(source, k, ent, found, c, doc):
	print('load', k[0], source)
	print('k', k)
	c.execute("SELECT data FROM " + source + " WHERE id = ?", (str(k[0]),))
	begriffe = [meta_kw(x) for x in json.loads(c.fetchone()[0])]

	over_threshold = []
	over_threshold_sm = []
	for begriff in begriffe:
		for token in doc:
			if token.is_alpha:
				begriff.check_word(token.text)
		if begriff.relevance > 0.5:
			over_threshold.append(begriff)
		if begriff.relevance > 0.02:
			over_threshold_sm.append(begriff)			

	normdaten_checked = []
	for begriff in over_threshold:
		c.execute("SELECT pageid, normdaten FROM articles WHERE title = ?", (begriff.title,))
		normdaten = c.fetchone()[1]
		if (ent.label_ in label_normadaten and label_normadaten[ent.label_] == k[3]) or (ent.label_ == 'MISC' and normdaten not in ['p', 'g', 'k']):
			normdaten_checked.append(begriff)


	kw_found = False
	if len(normdaten_checked) > 1:
		for begriff in normdaten_checked:
			if (len(begriff.title) > 4 and Levenshtein.ratio(begriff.title, ent.text) > 0.9) or begriff.title == ent.text:
				kw_found = True
				found.append(Keyword(title=begriff.title, c=c, synonyme=[ent.text]))

		# Nimm das KW mit den meisten Views
		if kw_found == False:
			most_views = 0
			approved = None
			for begriff in normdaten_checked:
				c.execute("SELECT views FROM articles WHERE title = ?", (begriff.title,))
				views = c.fetchall()[0][0]
				if views > most_views:
					most_views = views
					approved = begriff
			# Steht für alle Begriffe in normdaten_checked keine views zur Verfügung, bleibt approved None
			if approved:
				found.append(Keyword(title=approved.title, c=c, synonyme=[ent.text]))

	elif len(normdaten_checked) == 1:
		found.append(Keyword(title=over_threshold[0].title, c=c, synonyme=[ent.text]))

	else:
		for begriff in over_threshold_sm:
			if (len(begriff.title) > 4 and Levenshtein.ratio(begriff.title, ent.text) > 0.9) or begriff.title == ent.text:

				c.execute("SELECT pageid, normdaten FROM articles WHERE title = ?", (begriff.title,))
				normdaten = c.fetchone()[1]
				if (ent.label_ in label_normadaten and label_normadaten[ent.label_] == normdaten) or (ent.label_ == 'MISC' and normdaten not in ['p', 'g', 'k']) or True:
					kw_found = True
					found.append(Keyword(title=begriff.title, c=c, synonyme=[ent.text]))
					break



def analyze(ent, c, found, doc):
	kw_kandidat = search_kw_kandidat(ent, c, improved=None)

	# Papst Paul VI vs. Papst Paul VI.
	if kw_kandidat == []:
		if ent.text.split(' ')[-1].isupper():
			improved = ent.text + '.'
			kw_kandidat = search_kw_kandidat(ent, c, improved=improved)

	# Papst Paul VI vs. Papst Paul VI.
	if kw_kandidat == []:
		if ent.text.split(' ')[-1].isupper():
			improved = ent.text + '.'
			kw_kandidat = search_kw_kandidat(ent, c, improved=improved)

	# Zweiten Vatikanischen Konzil vs. Zweit Vatikanisch Konzil
	if kw_kandidat == []:
		if any(c.isupper() for c in ent.text):
			improved = []
			for word in ent.text.split(' '):
				if len(word) > 5 and word.endswith('en'):
					improved.append(word[:-2])
				elif len(word) > 5 and word.endswith('s'):
					improved.append(word[:-1])
				elif len(word) > 5 and word.endswith('em'):
					improved.append(word[:-2])
				else:
					improved.append(word)
			improved = " ".join(improved)
			if improved != ent.text:
				kw_kandidat = search_kw_kandidat(ent, c, improved=improved)

	new_kw_kandidat = []
	for k in kw_kandidat:
		if k not in new_kw_kandidat:
			new_kw_kandidat.append(k)
	kw_kandidat = new_kw_kandidat

	begriffsklärung = False
	for k in kw_kandidat:
		if k[2] == 1:
			begriffsklärung = True
			begriffsklaerung('context_sim', k, ent, found, c, doc)




	if begriffsklärung == False:
		if len(kw_kandidat) == 1 and not kw_kandidat[0][6]:
			k = kw_kandidat[0]
			if (ent.label_ in label_normadaten and label_normadaten[ent.label_] == k[3]) or (ent.label_ == 'MISC' and k[3] not in ['p', 'g', 'k']):
				found.append(Keyword(title=k[1], c=c, synonyme=[ent.text]))
		else:
			for k in kw_kandidat:
				if k[5]:	# falls norm_syn existiert
					begriffsklaerung('norm_syn', k, ent, found, c, doc)
					break
				elif k[6]:
					begriffsklaerung('alias_syn', k, ent, found, c, doc)
					break


def get_keywords(text):
	conn = sqlite3.connect('database.db')
	c = conn.cursor()

	print('nlp text', text)
	print()
	print()
	doc = nlp(text)

	kandidaten_text = []
	kandidaten_words = []

	found = []

	for ent in doc.ents:
		if ent.text not in kandidaten_text and len(ent.text) > 1:
			for token in ent:
				kandidaten_words.append(token.text)
			kandidaten_text.append(ent.text)
			analyze(ent, c, found, doc)

	no_normdaten1 = []
	no_normdaten2 = []
	for token in doc:
		if token.text not in kandidaten_text and token.text not in kandidaten_words and token.text[0].isupper() and (token.tag_ in ('NN', 'NE') or token.pos_ in ('NOUN', 'PROPN')):
			kandidaten_text.append(token.text)
			is_subj = False
			if token.is_sent_start:
				c.execute("SELECT 1 FROM wikt_words WHERE title = ?", (token.text.lower(),))
				r = c.fetchall()
				if len(r) == 0:
					is_subj = True
			else:
				c.execute("SELECT 1 FROM wikt_words WHERE title = ?", (token.text,))
				r = c.fetchall()
				if len(r) > 0:
					is_subj = True
				else:
					lowered = token.text
					lowered = lowered[0].lower() + lowered[1:]
					c.execute("SELECT 1 FROM wikt_words WHERE title = ?", (lowered,))
					r = c.fetchall()
					if len(r) == 0:
						is_subj = True

			if is_subj:
				c.execute("SELECT pageid, title, begriff, normdaten, views, norm_syn FROM articles WHERE title_norm = ?", (token.text,))
				r = c.fetchall()
				kw_found = False
				if len(r) == 1 and r[0][3] and ' ' not in r[0][1]:
					if not r[0][3]:
						no_normdaten1.append([r[0][1]])
					found.append(Keyword(title=r[0][1], c=c, synonyme=[token.text]))
					kw_found = True
				else:
					c.execute("SELECT articles.pageid, title, begriff, normdaten, views, norm_syn FROM redirects INNER JOIN articles ON articles.pageid = redirects.redirects_to WHERE redirects_from = ?", (token.text,))
					r = c.fetchall()
					if len(r) == 1 and r[0][3] and ' ' not in r[0][1]:
						found.append(Keyword(title=r[0][1], c=c, synonyme=[token.text]))
						kw_found = True

				# Nominativ
				if kw_found == False:
					c.execute("SELECT title FROM wikt_words WHERE nom_sg=? OR nom_pl=? OR gen_sg=? OR gen_pl=? OR dat_sg=? OR dat_pl=? OR akk_sg=? OR akk_pl=?", [token.text for n in range(0,8)])
					r = c.fetchall()
					if len(r) == 1:
						nominativ = r[0][0]
						c.execute("SELECT pageid, title, begriff, normdaten, views, norm_syn FROM articles WHERE title_norm = ?", (nominativ,))
						r = c.fetchall()
						if len(r) == 1 and ' ' not in r[0][1]:
							kandidaten_text.append(nominativ)
							if not r[0][3]:
								no_normdaten2.append([r[0][1]])
							found.append(Keyword(title=r[0][1], c=c, synonyme=[token.text,nominativ]))
						else:
							c.execute("SELECT articles.pageid, title, begriff, normdaten, views, norm_syn FROM redirects INNER JOIN articles ON articles.pageid = redirects.redirects_to WHERE redirects_from = ?", (nominativ,))
							r = c.fetchall()
							if len(r) == 1 and r[0][3] and ' ' not in r[0][1]:
								kandidaten_text.append(nominativ)
								found.append(Keyword(title=r[0][1], c=c, synonyme=[token.text,nominativ]))

	found_ids = []
	found_kws = []
	text_copy = text.lower()
	syn_dict = {}
	kw_dict = {}

	for kw in found:
		if kw.pageid not in found_ids:
			found_kws.append(kw)
			found_ids.append(kw.pageid)
			kw_dict[kw.pageid] = kw

	for kw in found_kws:
		for syn in kw.synonyme:
			if ' ' in syn:
				occurences = len(re.findall(re.escape(syn), text_copy))
				text_copy = re.sub(re.escape(syn), '', text_copy)
				kw_dict[kw.pageid].add_to_occurences(occurences)
			else:
				syn_dict[syn] = kw.pageid

	doc2 = nlp(text_copy)
	for token in doc2:
		try:
			kw_dict[syn_dict[token.text]].add_to_occurences(1)
		except KeyError:
			pass

	result = []
	for value in kw_dict.values():
		if value.occurences == 0:
			value.add_to_occurences(1)
		result.append({'title': value.title,'occurences': value.occurences, 'synonyme': value.synonyme})
	return result