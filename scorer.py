"""CONLL Shared Task 2015 Scorer

"""
import argparse
import json
from confusion_matrix import ConfusionMatrix, Alphabet
import validator


def evaluate(gold_list, predicted_list):
	connective_cm = evaluate_connectives(gold_list, predicted_list)
	arg1_cm, arg2_cm, rel_arg_cm = evaluate_argument_extractor(gold_list, predicted_list)
	sense_cm = evaluate_sense(gold_list, predicted_list)

	print 'Explicit connectives--------------'
	print connective_cm.get_prf('yes')

	print 'Arg 1 extractor--------------'
	print arg1_cm.get_prf('yes')
	print 'Arg 2 extractor--------------'
	print arg2_cm.get_prf('yes')
	print 'Arg1 Arg2 extractor combined--------------'
	print rel_arg_cm.get_prf('yes')
	print 'Sense classification--------------'
	sense_cm.print_summary()
	print 'Overall parser performance --------------'
	print evaluate_relation(gold_list, predicted_list)


def evaluate_argument_extractor(gold_list, predicted_list):
	"""Evaluate argument extractor at Arg1, Arg2, and relation level

	"""
	gold_arg1 = [(x['DocID'], x['Arg1']['TokenList']) for x in gold_list]
	predicted_arg1 = [(x['DocID'], x['Arg1']['TokenList']) for x in predicted_list]
	arg1_cm = compute_binary_eval_metric(gold_arg1, predicted_arg1, span_exact_matching)

	gold_arg2 = [(x['DocID'], x['Arg2']['TokenList']) for x in gold_list]
	predicted_arg2 = [(x['DocID'], x['Arg2']['TokenList']) for x in predicted_list]
	arg2_cm = compute_binary_eval_metric(gold_arg2, predicted_arg2, span_exact_matching)

	gold_arg12 = [(x['DocID'], (x['Arg1']['TokenList'], x['Arg2']['TokenList'])) for x in gold_list]
	predicted_arg12 = [(x['DocID'], (x['Arg1']['TokenList'], x['Arg2']['TokenList']))
			for x in predicted_list]
	rel_arg_cm = compute_binary_eval_metric(gold_arg12, predicted_arg12, spans_exact_matching)
	return arg1_cm, arg2_cm, rel_arg_cm

def evaluate_connectives(gold_list, predicted_list):
	"""Evaluate connective recognition accuracy for explicit discourse relations

	"""
	explicit_gold_list = [(x['DocID'], x['Connective']['TokenList']) \
			for x in gold_list if x['Type'] == 'Explicit']
	explicit_predicted_list = [(x['DocID'], x['Connective']['TokenList']) \
			for x in predicted_list if x['Type'] == 'Explicit']
	connective_cm = \
		compute_binary_eval_metric(explicit_gold_list, explicit_predicted_list, span_exact_matching)	
	return connective_cm


def span_exact_matching(gold_span, predicted_span):
	"""Matching two spans

	Input:
		gold_span : a list of tuples :DocID and list of tuples of token addresses
		predicted_span : a list of tuples :DocID and list of token indices

	Returns:
		True if the spans match exactly
	"""
	gold_docID = gold_span[0]
	predicted_docID = predicted_span[0]
	gold_token_indices = [x[2] for x in gold_span[1]]
	predicted_token_indices = predicted_span[1]
	return gold_docID == predicted_docID and gold_token_indices == predicted_token_indices

def spans_exact_matching(gold_doc_id_spans, predicted_doc_id_spans):
	"""Matching two groups of spans

	Input:
		gold_doc_id_spans : (DocID , a list of lists of tuples of token addresses)
		predicted_doc_id_spans : (DocID , a list of lists of token indices)

	Returns:
		True if the spans match exactly
	"""
	exact_match = True
	gold_docID = gold_doc_id_spans[0]
	gold_spans = gold_doc_id_spans[1]
	predicted_docID = predicted_doc_id_spans[0]
	predicted_spans = predicted_doc_id_spans[1]

	for gold_span, predicted_span in zip(gold_spans, predicted_spans):
		exact_match = span_exact_matching((gold_docID,gold_span), (predicted_docID, predicted_span)) \
				and exact_match
	return exact_match


def span_partial_matching(gold_span, predicted_span):
	"""Overlapping in content words

	Still under construction
	"""
	pass

def evaluate_relation(gold_list, predicted_list):
	"""Evaluate relation accuracy

	"""
	gold_to_predicted_map, predicted_to_gold_map = \
			_link_gold_predicted(gold_list, predicted_list, spans_exact_matching)
	correct = 0.0
	for i, gold_relation in enumerate(gold_list):
		if i in gold_to_predicted_map:
			predicted_sense = gold_to_predicted_map[i]['Sense'][0]
			if gold_relation['Type'] == 'Explicit':
				predicted_connective = (0, gold_to_predicted_map[i]['Connective']['TokenList'])
				gold_connective = (0, gold_relation['Connective']['TokenList'])
				if predicted_sense in gold_relation['Sense'] and \
						span_exact_matching(gold_connective, predicted_connective):
					correct += 1
			else:
				if predicted_sense in gold_relation['Sense']:
					correct += 1
	precision = correct/len(predicted_list)
	recall = correct/len(gold_list)
	return (precision, recall, (2* precision * recall) / (precision + recall))

def evaluate_sense(gold_list, predicted_list):
	"""Evaluate sense classifier

	The label 'no' is for the relations that are missed by the system
	because the arguments don't match any of the gold relations.
	"""
	sense_alphabet = Alphabet()
	for relation in gold_list:
		sense_alphabet.add(relation['Sense'][0])
	sense_alphabet.add('no')
	sense_cm = ConfusionMatrix(sense_alphabet)
	gold_to_predicted_map, predicted_to_gold_map = \
			_link_gold_predicted(gold_list, predicted_list, spans_exact_matching)

	for i, gold_relation in enumerate(gold_list):
		if i in gold_to_predicted_map:
			predicted_sense = gold_to_predicted_map[i]['Sense'][0]
			if predicted_sense in gold_relation['Sense']:
				sense_cm.add(predicted_sense, predicted_sense)
			else:
				sense_cm.add(predicted_sense, gold_relation['Sense'][0])
		else:
			sense_cm.add('no', gold_relation['Sense'][0])

	for i, predicted_relation in enumerate(predicted_list):
		if i not in predicted_to_gold_map:
			sense_cm.add(predicted_relation['Sense'][0], 'no')
	return sense_cm


def combine_spans(span1, span2):
	"""Merge two text span dictionaries

	"""
	new_span = {}
	new_span['CharacterSpanList'] = span1['CharacterSpanList'] + span2['CharacterSpanList']
	new_span['SpanList'] = span1['SpanList'] + span2['SpanList']
	new_span['RawText'] = span1['RawText'] + span2['RawText']
	new_span['TokenList'] = span1['TokenList'] + span2['TokenList']
	return new_span

def compute_binary_eval_metric(gold_list, predicted_list, matching_fn):
	"""Compute binary evaluation metric

	"""
	binary_alphabet = Alphabet()
	binary_alphabet.add('yes')
	binary_alphabet.add('no')
	cm = ConfusionMatrix(binary_alphabet)
	matched_predicted = [False for x in predicted_list]
	for gold_span in gold_list:
		found_match = False
		for i, predicted_span in enumerate(predicted_list):
			if matching_fn(gold_span, predicted_span) and not matched_predicted[i]:
				cm.add('yes', 'yes')
				matched_predicted[i] = True
				found_match = True
				break
		if not found_match:
			cm.add('yes', 'no')
	# Predicted span that does not match with any
	for matched in matched_predicted:
		if not matched:
			cm.add('no', 'yes')
	return cm


def _link_gold_predicted(gold_list, predicted_list, matching_fn):
	"""Link gold standard relations to the predicted relations

	A pair of relations are linked when the arg1 and the arg2 match exactly.
	We do this because we want to evaluate sense classification later.

	Returns:
		A tuple of two dictionaries:
		1) mapping from gold relation index to predicted relation index
		2) mapping from predicted relation index to gold relation index
	"""
	gold_to_predicted_map = {}
	predicted_to_gold_map = {}
	gold_arg12_list = [(x['DocID'], (x['Arg1']['TokenList'], x['Arg2']['TokenList']))
			for x in gold_list]
	predicted_arg12_list = [(x['DocID'], (x['Arg1']['TokenList'], x['Arg2']['TokenList']))
			for x in predicted_list]
	for gi, gold_span in enumerate(gold_arg12_list):
		for pi, predicted_span in enumerate(predicted_arg12_list):
			if matching_fn(gold_span, predicted_span):
				gold_to_predicted_map[gi] = predicted_list[pi]
				predicted_to_gold_map[pi] = gold_list[gi]
	return gold_to_predicted_map, predicted_to_gold_map


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Evaluate system's output against the gold standard")
	parser.add_argument('gold', help='Gold standard file')
	parser.add_argument('predicted', help='System output file')
	args = parser.parse_args()
	gold_list = [json.loads(x) for x in open(args.gold)]
	validator.validate(args.predicted)
	predicted_list = [json.loads(x) for x in open(args.predicted)]
	evaluate(gold_list, predicted_list)

