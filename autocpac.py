"""
Robert Kim
Python 3
"""

import argparse
import csv
import glob
import itertools
import numpy as np
import os
import os.path as op
import pandas as pd
import re
import shutil
import subprocess
import yaml

parser = argparse.ArgumentParser(description="CPAC subject list generation and exectuion")
parser.add_argument('-r', '--rewrite', action='store_true', help="clear output directory and force run 3dinfo")
args = parser.parse_args()


def main():
	"""sorting and analysis of structural and functional MRI files via CPAC"""

	if args.rewrite or not op.exists(outdir):
		shutil.rmtree(outdir, ignore_errors=True)
		print("\n::: CREATING NEW {} OUTPUT DIRECTORY :::".format(outdir))
		os.makedirs(outdir)

	flist = glob.glob(op.join(outdir, '*.txt'))
	if not flist:
		print("\n::: GENERATING CPAC SUBJECT LIST TEXT FILES :::".format(outdir))
		run_3dinfo()
		flist = glob.glob(op.join(outdir, '*.txt'))
		run_cpac_setup()


def run_3dinfo():
	"""generates .txt files sorted by the TR and TR-count values given by `3dinfo` into the output directory"""

	# find concatenated resting state fMRI files
	paths = [op.join(homedir, x) for x in ['adult', 'adolescent', 'child']]
	
	flist = []
	for root, dirs, files in itertools.chain.from_iterable(os.walk(x) for x in paths):
		for f in files:
			if '3T' in root and 'REST_ALL' in f and f.endswith('.nii.gz'):
				flist.append([root, f])

	# run `3dinfo` to extract TR and TR-count information
	output = []
	for x in flist:
		fpath = op.relpath(op.join(x[0], x[1]), homedir)
		temp = fpath.split('/')
		[pardir, subjname, filename] = [temp[0], temp[1], temp[-1]]	

		funcout = subprocess.check_output(['3dinfo', fpath]).decode('utf-8')
		s0 = funcout.index('Number of time steps')
		sList = [s0 for n in range(4)]
		for i in range(1, 4):
			sList[i] = funcout.index('=', sList[i-1] + 1)

		TRnum = int(re.findall('\d+', funcout[sList[1]:sList[2]]).pop())
		TRdur = float(re.findall('(?:(?:0|[1-9][0-9]*)(?:\.[0-9]*)?|\.[0-9]+)', funcout[sList[2]:sList[3]]).pop())

		output.append([pardir, subjname, filename, TRnum, TRdur])

	# find subject files missing concatenated resting state fMRI files
	subjlist = list(itertools.chain.from_iterable(next(os.walk(x))[1] for x in paths))
	print("\n::: MISSING CONCATENATED FILES :::")
	for x in subjlist:
		if not any(x in y[1] for y in flist):
			print("\t{}".format(x))

	'''
	# write output to csv file
	fieldnames = ['dir', 'subj', 'file', 'TRcount', 'TR']
	with open(op.join(outdir, '3dinfo_TRs.csv'), 'w') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames = fieldnames)
		writer.writeheader()
		
		for row in output:
			writer.writerow({fieldnames[n]:row[n] for n in range(len(row))})
	'''

	# sort, group, and output to text file by subject, TR, and TR-count
	df = pd.DataFrame(output, columns=fieldnames)
	del df['file']
	df = df.sort_values(['dir', 'TRcount', 'TR'], ascending=[1, 1, 1])
	gb = df.groupby(['dir', 'TRcount', 'TR'])
	
	for group in [gb.get_group(x) for x in gb.groups]:
		groupspec = list(group.iloc[0].values)
		del groupspec[1]
		np.savetxt(op.join(outdir, '%s_%d_%.3fs.txt' % tuple(groupspec)), group['subj'].values, fmt='%s')


def run_cpac_setup():
	"""generates .yml configuration files for `cpac_setup.py` and respective `cpac_setup.py` .csv file outputs into the output directory"""

	cfg = op.join(outdir, 'data_config.yml')
	os.chdir(outdir)

	# edit .yml file and run `cpac_setup.py`
	for f in flist:
		print("\n::: RUNNING cpac_setup.py FOR {} :::".format(f))
		f_base = op.basename(f)
		pardir = f_base[ :f_base.index('_')]
		anatdir = op.join(homedir, '{}/{{participant}}/unprocessed/3T/T1w_MPR1/{{participant}}_3T_T1w_MPR1.nii.gz'.format(pardir))
		funcdir = op.join(homedir, '{}/{{participant}}/unprocessed/3T/{{participant}}_3T_rfMRI_REST_ALL_AP.nii.gz'.format(pardir))
		ymldata = {
			'dataFormat': ['Custom'],
			'bidsBaseDir': None,
			'anatomicalTemplate': anatdir,
			'functionalTemplate': funcdir,
			'subjectList': f,
			'exclusionSubjectList': None,
			'siteList': None,
			'scanParametersCSV': None,
			'awsCredentialsFile': None,
			'outputSubjectListLocation': outdir,
			'subjectListName': f_base[ :-4],
			}

		with open(cfg, 'w') as ymlfile:
			yaml.dump(ymldata, ymlfile)

		subprocess.call(['cpac_setup.py', cfg])


if __name__ == '__main__':
	homedir = op.dirname(op.abspath(__file__))
	os.chdir(homedir)

	outdir = op.join(homedir, 'cpac')

	main()

	print("\n ::: COMPLETED :::\n")
