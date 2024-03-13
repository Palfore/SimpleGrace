""" Provides a simple python wrapper for the xmgrace plotting software.
	
	This implementation provides a single function call for plot generation.
	Xmgrace is well-know for it's high quality and well-established use case in scientific plotting.
	Although there are more complete packages, such as [pygrace](https://pypi.org/project/pygrace/),
	the simplicity and ease of use are the key points here.

	Despite the high quality plots, the functionality and ability to dynamically generate plots is difficult.
	This provides a way to easily generate figures programmatically, leaving the graphical design to the xmgrace GUI.
	Additionally, to reduce errors, the data generating code should be connected directly to the graphing software,
	so there are no 'translation' issues. So, the values are updated by this software, but the visuals must be done manually.

	This facilitates a workflow where you programmatically generate the data, then work within the interface to set up the visuals.
	If the data changes, running the function will update the data - not the visuals. It is ideal for the data to be generated, 
	while a GUI is easier to use for the visuals.

	There are some considerations when adding/removing groups or sets after the initial generation.
		- When removing groups/sets, there will be vestigial @lines regarding that group/set's formatting
		- In addition to this, the formatting may get shifted: if S0 is deleted, S1 may have the aesthetics of the now removed S0.
		- It may take two passes to update the legend.
		- It is best to know the shape of the final plot upfront.

"""

from shutil import copyfile, which
from pprint import pprint
from pathlib import Path
import difflib
import filecmp
import time
import ast
import os
import re

def get_longest_string_length(strings):
	if not strings:
		return 0
	return max([len(string) for string in strings])

def remove_chars(string: str, chars: str=",()[]'"):
	return ''.join(c for c in str(string) if c not in chars)

def ask_prompt(question, opps="Sorry, I did not understand your response. Please Try Again. ", default=None):
	''' Prompts the user with a question until a valid response is given.
		This should be called confirm.
		@param question The message to prompt the user with.
		@param oops The message to give to the user if they give an invalid response.
		@note A valid response is either an AFFIRMATIVE_ANSWERS or NEGATIVE_ANSWERS. '''	
	
	AFFIRMATIVE_ANSWERS = ["yes", "y", "t"]
	NEGATIVE_ANSWERS = ["no", "n", "f"]

	def isAffirmative(answer):
		''' Determines if the answer is affirmative. 
			@param answer The response to be checked. 
			@return boolean representing whether the answer if affirmative or not. '''
		return any(answer.lower() == s for s in AFFIRMATIVE_ANSWERS)

	def isNegative(answer):
		''' Determines if the answer is negative. 
			@param answer The response to be checked.
			@return boolean representing whether the answer is negative or not. '''
		return any(answer.lower() == s for s in NEGATIVE_ANSWERS)

	if default is None:
		while True:
			response = input(question)
			if isAffirmative(response):
				return True
			elif isNegative(response):
				return False
			else:
				print(opps)
	else:
		response = input(question)
		if isAffirmative(response):
			return True
		elif isNegative(response):
			return False
		else:
			return default


def get_file_differences(v1, v2):
	''' Compares the content from two .agr files, ignoring time stamps. '''
	lines1 = [l for l in v1 if not (
				l.startswith('@timestamp def "') or
				l.startswith('@description "Last Updated: ') )]
	lines2 = [l for l in v2 if not (
				l.startswith('@timestamp def "') or
				l.startswith('@description "Last Updated: ') )]
	return difflib.context_diff(lines1, lines2)


def find_xmgrace_folder():
	""" Finds and returns the location of the "Default.arg" file. """
	possible_paths = [
	    "/usr/share/grace/templates/Default.agr",
	    "/usr/local/share/grace/templates/Default.agr",
	    "/usr/local/grace/templates/Default.agr",
	    "C:/Program Files/Grace/templates/Default.agr",
	    "C:/Program Files (x86)/Grace/templates/Default.agr",
	]

	for path_str in possible_paths:
	    path = Path(path_str)
	    if path.exists():
	        return path
	
	return None

class XMGrace:
	""" Provides a wrapper around some common xmgrace related functions.'

	On linux, xmgrace can be installed with `sudo apt-get install grace`
	The user should add the contents of `Environment/xmgrace/grace/gracerc.user` to `.grace/gracerc.user`.
	This will apply important defaults.
	"""
	TEMPLATE_PATH = find_xmgrace_folder()
	STARTING_LINE = "# Grace project file\n"
	PRECISION = 8

	def __init__(self, xmgrace_file: str):
		self.path = xmgrace_file


	def open(self):
		""" Opens the current file in xmgrace. """
		if not self.is_valid_file():
			raise ValueError("The gracefile you specified seems incorrect.")

		if which('xmgrace') is None:
			raise ValueError("xmgrace is not installed, it can be installed on linux with `sudo apt-get install grace`.")
		os.system(f"xmgrace {self.path}")

	def is_valid_file(self):
		""" Returns whether the current file is a valid xmgrace file. """
		with open(self.path, 'r') as f:
			return f.readline() == "# Grace project file\n"

	def create_pdf(self, create_eps: bool=True):
		""" Creates a `.pdf` from a `.agr` file.

		Args:
			agr_file_path: The path to the `.agr` file.
			create_eps: Whether a `.eps` should also be created which may be a useful
				alternative and is a byproduct of the pdf creation process.

		Note:
			The following command line applications are required:

			* `gracebat` This should be installed with xmgrace.
			* `epstopdf` On linux install with: `sudo apt install texlive-font-utils`
			* `pdfcrop` On linux install with: `sudo apt install texlive-extra-utils`
		"""

		dirname, basename = os.path.split(self.path)
		pre, ext = os.path.splitext(basename)
		prefix = os.path.join(dirname, 'fig_' + pre)

		if which('gracebat') is None:
			raise ValueError('gracebat is not installed.')
		os.system(f'gracebat {self.path} -printfile {prefix+".eps"}')

		if which('epstopdf') is None:
			raise ValueError('epstopdf is not installed.')
		os.system(f'epstopdf {prefix+".eps"}')

		if which('pdfcrop') is None:
			raise ValueError('pdfcrop is not installed.')
		os.system(f'pdfcrop {prefix+".pdf"}')

		os.system(f'mv {prefix+"-crop.pdf"} {prefix+".pdf"}')

		if not create_eps:
			os.sytem(f'rm {prefix+".eps"}')

	def get_data_portion(self):
		""" Returns the data portion of the xmgrace file in the format:
				[(Group#, Section#, datatype, [
					data1, data2, data3, ...
				])]
			where dataN is a tuple of values, and datatype is like: xydy, xy. """
		data = []
		reading = None
		for line in open(self.path):
			line = line.strip()

			if line.startswith("@target G"):
				G, S = line.split()[1].split('.')
				reading = (int(G[1:]), int(S[1:]))
				data.append([*reading, None, []])
				continue

			if reading is not None:
				if line.startswith('@type '):
					data[-1][2] = line.replace('@type ', '')
					continue

				if line == "&":
					reading = None
					continue

				data[-1][-1].append(tuple(ast.literal_eval(e) for e in line.split()))
		return data


	@staticmethod
	def clean_entry(entry: list):
		reformatted_entry = []
		for datum in entry:
			if 'inf' in str(datum).lower() or 'nan' in str(datum).lower():
				print('Graph skipping {entry} due to inf value.')
				return ''
			try:
				if isinstance(datum, float):
					datum = f"{datum:.{XMGrace.PRECISION}}"
					if float(datum) == int(float(datum)):  # No decimals
						datum = str(int(float(datum)))  # xmgrace removes .0's
				elif isinstance(datum, str):
					datum = f'"{datum}"'  # Strings need to be surrounded in double quotes
				reformatted_entry.append(datum)
			except ValueError as e:
				if str(e) == 'cannot convert float NaN to integer':
					print(f'Graph skipping {entry} in plot due to nan value')
					return ''
				raise ValueError(e, entry)
			except OverflowError as e:
				if str(e) == 'OverflowError: cannot convert float infinity to integer':
					print(f'Skipping skipping {entry} in plot due to overflow')
					return ''
		return remove_chars(str(reformatted_entry)) + '\n'

class Set:
	def __init__(self, index: int, label: str, datatype: str, entries: list):
		self.label = label
		self.datatype = datatype
		self.entries = entries

	def __str__(self):
		return ''.join(self.as_list())

	def as_list(self):
		return [
			f"@type {self.datatype}\n",
			*[XMGrace.clean_entry(entry) for entry in self.entries]
		]

class Group:
	def __init__(self, index: int, label: str, sets: list):
		self.index = index
		self.label = label
		self.sets = sets

	def __str__(self):
		return '\n'.join([
			f"@target G{self.index}.S{set_index}\n" + str(s) + '\n&' for set_index, s in enumerate(self.sets)
		])

	def as_list(self):
		lines = []
		for set_index, s in enumerate(self.sets):
			lines.append(f"@target G{self.index}.S{set_index}\n")
			lines.extend(s.as_list())
			lines.append('&\n')
		return lines

class Graph:
	def __init__(self, figure_path: str, description: str, datasets: list, prompt: bool=None):
		""" Plot the datasets in xmgrace
		
		Args:
			prompt: Whether xmgrace should be opened.
				None means the user will be prompted.
				A boolean value determines whether xmgrace is automatically opened. 


		A common pattern is to plot a dictionary:
		```
			('set name', 'xy', list(zip(errs.items())))
		```
		"""
		self.path = figure_path
		self.prompt = prompt

		description_lines = description.expandtabs().split('\n')
		length = get_longest_string_length(description_lines)
		divider = '"' + '='*length + '"\n'
		self.description = [
			f'''@description "Last Updated: {time.strftime("%A %B %d, %Y at %I:%M%p")}"\n''',
			f'@description ' + divider,
			*[f'@description "{l:{length}}"\n' for l in description_lines if l],
			f'@description ' + divider,
		]

		self.data = []
		self.subtitle = {}
		self.legend = {}
		for G_i, (G_label, groups) in enumerate(datasets):
			G_label = '' if G_label is None else G_label
			self.subtitle[G_i] = f'@    subtitle "{G_label}"\n'
			self.legend[G_i] = {}

			set_objects = []
			for S_i, (S_label, datatype, sets) in enumerate(groups):
				S_label = '' if S_label is None else S_label
				self.legend[G_i][S_i] = f'@    s{S_i} legend  "{S_label}"\n'
				set_objects.append(Set(S_i, S_label, datatype, sets))

			self.data.append(Group(G_i, G_label, set_objects))
		self.create_file()

	def create_file(self):
		""" 1) Create path to file
			2) Create a template, or use previous version
			3) Update it to contain the callers information
			4) Check for differences, and prompt the user to open the file. """
		directory, file_name = os.path.split(self.path)
		if directory:
			os.makedirs(directory, exist_ok=True)

		if not os.path.exists(self.path):
			copyfile(XMGrace.TEMPLATE_PATH, self.path)
			print(f"An xmgrace file template was created at {self.path}")

		lines = []
		with open(self.path, 'r') as f:
			data_portion_found = False
			legend_portion_found = False
			group = None
			section = None

			original_lines = f.readlines()
			for line in original_lines:
				# Get the current group
				if line.startswith('@with g'):
					group = int(line.replace('@with g', ''))

				# Update the set's legend
				if re.search(r'\@    s\d legend  \"', line):
					assert group is not None, "No group (@with g#) was found in the file, before a legend."
					s = int(re.findall(r'\d+', line)[0])
					if group in self.legend and s in self.legend[group]:
						lines.append(self.legend[group][s])
					continue

				# Update the group's subtitle
				if line.startswith('@    subtitle "'):
					if group in self.subtitle:
						lines.append(self.subtitle[group])
					continue

				# Update data portion when you see the first data or ... [see else below]
				if line.startswith("@target G"):
					lines.extend(sum((g.as_list() for g in self.data), []))
					break

				# Erase Old Description
				if line.startswith('@description'):
					continue

				# Write normal lines
				lines.append(line)

				# Add new description
				if self.description and line.startswith("@page size "):
					lines.extend(self.description)

			else:  # ... if you never found a data portion, create it
				for G_i, subtitle in self.subtitle.items():
					lines.append(f'@with g{G_i}\n')
					lines.append(subtitle)
					for S_i, legend in self.legend[G_i].items():
						lines.append(legend)
				lines.extend(sum((g.as_list() for g in self.data), []))

		with open(self.path, 'w') as f:
			f.write(''.join(lines))

		differences = list(get_file_differences(original_lines, lines))
		if differences:
			print("There are some file changes:")
			pprint(differences)
		else:
			print("No changes were made since the previous file was created.")

		xmgrace = XMGrace(self.path)
		if self.prompt is not None:
			if self.prompt:
				xmgrace.open()
		elif ask_prompt("Would you like to open the file in xmgrace? [y]", default=True):
			xmgrace.open()
		xmgrace.create_pdf()

if __name__ == '__main__':
	Graph('examples/after_edit/testing.agr', "This is an example.", [
		("group1", [
			("alternating", 'xy', [
				(.1, -.1),
				(.2, .4),
				(.3, -.9),
				(.4, 1.6),
			]),
			("increasing", 'xydy', [
				(.1, .1, .5),
				(.2, .4, .5),
				(.3, .9, .5),
				(.4, 1.6, .5),
			])
		]),
		("group2", [
			("set1", 'xy', [
				(.1, -.1),
				(.2, .4),
				(.3, -.9),
				(.4, 1.6),
			]),
			("set2", 'xydy', [
				(.1, .1, .5),
				(.2, .4, .5),
				(.3, .9, 5),
				(.4, 1.6, .5),
			])
		])
	])
