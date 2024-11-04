import glob
import re
import pandas as pd
import json
import os



def transform_json_to_df(input_fp, output_fp, col_mapping, value_nested=True):
    """ Produces a csv saved dataframe from a json file or jsv file"""
    # df = pd.DataFrame(pd.read_json(input_fp, lines=True).melt().dropna().value.to_list())
    # df = pd.DataFrame(df[col_mapping.keys()], copy=True).rename(columns=col_mapping)
    with open(input_fp) as source_file:
        if value_nested:
            df = pd.concat([
                pd.json_normalize(json.loads(line)['value'])
                for line in source_file.readlines()])
        else:
            df = pd.concat([
                pd.DataFrame(json.loads(line), index=[0])
                for line in source_file.readlines()], ignore_index=True)
    
        if df.empty:
            # Wenn das DataFrame leer ist, überspringe die Datei
            return

    df = pd.DataFrame(df[col_mapping.keys()], copy=True).rename(columns=col_mapping)
    df = df.drop_duplicates()
    df.to_csv(output_fp)


def transform_json_to_df_for_each_in_directory(input_dir, output_dir, col_mapping, value_nested=True):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    input_dir_entries = os.listdir(input_dir)
    for entry in input_dir_entries:
        if not os.path.isdir(os.path.join(input_dir, entry)):
            # Handling files in input_dir
            transform_json_to_df(
                input_fp=os.path.join(input_dir, entry),
                output_fp=os.path.join(output_dir, entry.replace('.json', '.csv')),
                col_mapping=col_mapping,
                value_nested=value_nested
            )
        else:
            transform_json_to_df_for_each_in_directory(
                input_dir=os.path.join(input_dir, entry),
                output_dir=os.path.join(output_dir, entry),
                col_mapping=col_mapping,
                value_nested=value_nested
            )


def filter_from_dict_string(input_fp, output_fp, dictionary):
    """ Filters CSV based on a dictionary with values for columns
        If a rows value is not in the list for that column, the row will be dropped
    """
    global_dict = json.loads(dictionary)
    df = pd.read_csv(input_fp, index_col=0)
    for key, value in global_dict.items():
        df = df[df[key].isin(value)]
    df.to_csv(output_fp)


def merge_dataframes_from_directory(input_dir_template, output_fp):
    def extract_attributes_from_path(template, path):
        """
        >>>extract_attributes_from_path('/ABC/{attr_1}/DEF/{attr_2}/','/ABC/abc/DEF/def/')
        {'attr_1': 'abc', 'attr_2': 'def'}
        """
        template_parts = [re.sub('\.[a-z]+', '', entry) for entry in input_dir_template.split('/')]
        path_parts = [re.sub('\.[a-z]+', '', entry) for entry in path.split('/')]
        template_path_parts = zip(template_parts, path_parts)

        attr_dict = {entry[0].replace('{', '').replace('}', ''): re.sub('\.[a-z]*', '', entry[1])
                     for entry in template_path_parts if entry[0].startswith('{') and entry[0].endswith('}')}
        return attr_dict

    generic_input_template = re.sub('{[^}]*}', '*', input_dir_template)
    file_list = glob.glob(generic_input_template)

    frames = []
    for file in file_list:
        attribute_values = extract_attributes_from_path(input_dir_template, file)
        print(attribute_values)
        df = pd.read_csv(file, index_col=0)
        for attr, val in attribute_values.items():
            df[attr] = val
        frames.append(df)
    print(frames)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates()
    df.to_csv(output_fp)