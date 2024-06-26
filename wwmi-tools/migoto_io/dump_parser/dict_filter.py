
import operator

from typing import Union, List
from enum import Enum, auto
from dataclasses import dataclass


class FilterCondition(Enum):
    AND = auto()
    OR = auto()


@dataclass
class Filter:
    condition: FilterCondition = FilterCondition.AND
    keys: Union[list, str] = None
    attributes_condition: FilterCondition = FilterCondition.AND
    attributes: dict = None
    dictionaries_condition: FilterCondition = FilterCondition.AND
    dictionaries: Union[list, dict, List['Filter']] = None


class DictFilter:
    def __init__(self, filter):
        self.filter = self.validate_filter(filter)
        self.filtered_dict = self.get_filtered_dict(self.filter)

    def validate_filter(self, filter):

        if not filter.condition:
            raise ValueError(f'Invalid filter: no merge condition specified"!')

        if not isinstance(filter.condition, FilterCondition):
            raise ValueError(
                f'Invalid filter: expected "FilterCondition" type for condition, got "{type(filter.condition)}"!')

        if not isinstance(filter.dictionaries_condition, FilterCondition):
            raise ValueError(
                f'Invalid filter: expected "FilterCondition" type for dictionaries_condition, got "{type(filter.dictionaries_condition)}"!')
        if not isinstance(filter.dictionaries, list):
            filter.dictionaries = [filter.dictionaries]

        for i, dictionary in enumerate(filter.dictionaries):
            if isinstance(dictionary, Filter):
                filter.dictionaries[i] = self.validate_filter(dictionary)
                continue
            if not isinstance(dictionary, dict):
                raise ValueError(
                    f'Invalid filter: expected "dict" or "Filter" type for dictionaries, got "{type(dictionary)}"!')

        if filter.keys is not None:
            if not isinstance(filter.keys, list):
                filter.keys = [filter.keys]

        if filter.attributes_condition is not None:
            if not isinstance(filter.attributes_condition, FilterCondition):
                raise ValueError(
                    f'Invalid filter: expected "FilterCondition" type for attributes_condition, got "{type(filter.attributes_condition)}"!')

            for attribute, values in filter.attributes.items():
                if len(attribute.strip()) == 0:
                    raise ValueError(f'Invalid filter: attribute "{attribute}" has no non-whitespace characters!')

            for dictionary in filter.dictionaries:
                if isinstance(dictionary, Filter) or len(dictionary) == 0:
                    continue

                first_dict_entry = next(iter(dictionary.values()))

                for attribute, values in filter.attributes.items():
                    parts = attribute.split(':')
                    attribute_name = parts[0]

                    if attribute_name.startswith('!'):
                        attribute_name = attribute_name[1:]

                    try:
                        attr = operator.attrgetter(attribute_name)(first_dict_entry)
                    except Exception:
                        raise ValueError(f'Invalid filter: data_dict member has no "{parts[0]}" attribute!')

                    if len(parts) == 2:
                        if not isinstance(attr, Union[list, dict]):
                            raise ValueError(f'Invalid filter: {attribute} is not iterable!')

                        attribute_name = parts[1]

                        if attribute_name.startswith('!'):
                            attribute_name = attribute_name[1:]

                        if '__key__' not in attribute_name:
                            try:
                                operator.attrgetter(attribute_name)(
                                    next(iter(attr.values())) if isinstance(attr, dict) else attr[0])
                            except Exception:
                                raise ValueError(f'Invalid filter: {attribute} member has no "{attribute_name}" attribute!')
                    elif len(parts) > 2:
                        raise ValueError(f'Invalid filter: more than one instance of ":" is not supported!')

                    if not isinstance(values, list):
                        filter.attributes[attribute] = [values]

        return filter

    def intersection(self, list1, list2):
        return [value for value in list1 if value in list2]

    def get_filtered_dict(self, filter, data_dict=None):
        result = {}

        # Optional usage of self.dict allows to compare external dict against default nested-filtered one
        if data_dict is None:
            # Build a list of external dicts and dicts resulting from nested filters
            dictionaries = []
            for dictionary in filter.dictionaries:
                if isinstance(dictionary, Filter):
                    dictionary = self.get_filtered_dict(dictionary)
                dictionaries.append(dictionary)
            # Apply dictionaries filter condition
            found = {}
            if filter.dictionaries_condition == FilterCondition.AND:
                found = dictionaries[0]
                for i in range(1, len(dictionaries)):
                    found = {key: found[key] for key in self.intersection(dictionaries[i].keys(), found.keys())}
            elif filter.dictionaries_condition == FilterCondition.OR:
                for dictionary in dictionaries:
                    found.update(dictionary)
            # Override default dict
            data_dict = found

        # Filter by keys
        if filter.keys:
            if len(filter.keys) > 0:
                found = {}
                for key in self.intersection(filter.keys, data_dict.keys()):
                    found[key] = data_dict[key]
                if filter.condition == FilterCondition.AND:
                    if len(found) == 0:
                        result = {}
                    else:
                        result.update(found)
                elif filter.condition == FilterCondition.OR:
                    result.update(found)

        # Filter by attributes of entries
        if filter.attributes_condition:
            dictionaries = []
            for filter_attribute, filter_values in filter.attributes.items():
                dictionary = {}
                for dict_key, dict_entry in data_dict.items():

                    parts = filter_attribute.split(':')

                    attribute_name = parts[0]

                    # If attribute name has '!' prefix, search for values that aren't in 'filter_values'
                    must_contain_value = True
                    if attribute_name.startswith('!'):
                        must_contain_value = False
                        attribute_name = attribute_name[1:]

                    attribute_value = operator.attrgetter(attribute_name)(dict_entry)

                    if len(parts) == 1:
                        # Check if given value of object's attribute is among 'filter_values' we're looking for
                        if self.has_value(must_contain_value, attribute_value, filter_values):
                            dictionary[dict_key] = dict_entry

                    elif len(parts) == 2:
                        # Check if any value in dict-type object's attribute is among 'filter_values' we're looking for
                        detected = False
                        for key, value in attribute_value.items() if isinstance(attribute_value, dict) else enumerate(attribute_value):

                            filter_attribute_name = parts[1]

                            # If attribute name has '!' prefix, search for values that aren't in 'filter_values'
                            must_contain_value = True
                            if filter_attribute_name.startswith('!'):
                                must_contain_value = False
                                filter_attribute_name = filter_attribute_name[1:]

                            if filter_attribute_name == '__key__':
                                # Search by dict key
                                if self.has_value(must_contain_value, key, filter_values):
                                    detected = True
                                    break
                            else:
                                # Search by attribute of object contained in dict value
                                value_attribute = operator.attrgetter(filter_attribute_name)(value)
                                if self.has_value(must_contain_value, value_attribute, filter_values):
                                    detected = True
                                    break

                        if detected:
                            dictionary[dict_key] = dict_entry

                dictionaries.append(dictionary)

            if filter.condition == FilterCondition.AND:
                found = dictionaries[0]
                for i in range(1, len(dictionaries)):
                    found = {key: found[key] for key in self.intersection(dictionaries[i].keys(), found.keys())}
                result.update(found)

            elif filter.condition == FilterCondition.OR:
                for dictionary in dictionaries:
                    result.update(dictionary)

        return result

    @staticmethod
    def has_value(must_contain_value, attribute_value, filter_values):
        if must_contain_value:
            if attribute_value in filter_values:
                return True
        else:
            if attribute_value not in filter_values:
                return True
        return False



