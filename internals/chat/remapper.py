"""
MIT License

Copyright (c) 2020-present xenova

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__all__ = ("Remapper",)


class Remapper:
    """Class used to control the remapping of one dictionary to another dictionary."""

    def __init__(self, new_key=None, remap_function=None, to_unpack=False):
        """Create a Remapper object
        :param new_key: The new key of the item, defaults to None
        :type new_key: str, optional
        :param remap_function: The remapping function, defaults to None
        :type remap_function: function, optional
        :param to_unpack: Unpack the remapped item (to map to multiple output keys),
            defaults to False
        :type to_unpack: bool, optional
        :raises ValueError: if unable to perform a remapping
        """

        if new_key is not None and to_unpack:
            # New key is specified, but must unpack. Not allowed
            raise ValueError("If to_unpack is True, new_key may not be specified.")

        self.new_key = new_key

        if isinstance(remap_function, staticmethod):
            remap_function = remap_function.__func__

        if remap_function is None or not (hasattr(remap_function, "__call__")):
            raise ValueError("remap_function must be callable or None.")

        self.remap_function = remap_function
        self.to_unpack = to_unpack

    @staticmethod
    def remap(
        info,
        remapping_dict,
        remap_key,
        remap_input,
        keep_unknown_keys=False,
        replace_char_with_underscores=None,
    ):
        """A function used to remap items from one dictionary to another
        :param info: Output dictionary
        :type info: dict
        :param remapping_dict: Dictionary of remappings
        :type remapping_dict: dict
        :param remap_key: The key of the remapping
        :type remap_key: str
        :param remap_input: The input sent to the remapping function
        :type remap_input: object
        :param keep_unknown_keys: If no remapping is found, keep the data
            with its original key and value. Defaults to False
        :type keep_unknown_keys: bool, optional
        :param replace_char_with_underscores: If no remapping is found,
            replace a character in the key with underscores. Defaults to None
        :type replace_char_with_underscores: str, optional
        :raises ValueError: if attempting to unpack an item that is not a dictionary,
            or if an unknown remapping is specified
        """

        remap = remapping_dict.get(remap_key)

        if remap:  # A matching 'remapping' has been found, apply this remapping
            if isinstance(remap, Remapper):
                new_key = remap.new_key  # or remap_key

                # Perform transformation
                if remap.remap_function:  # Has a remap function
                    new_value = remap.remap_function(remap_input)
                else:  # No remap function specified, apply identity transformation
                    new_value = remap_input

                # Assign values to info
                if not remap.to_unpack:
                    info[new_key] = new_value
                elif isinstance(new_value, dict):
                    info.update(new_value)
                else:
                    raise ValueError("Unable to unpack item which is not a dictionary.")

            elif isinstance(remap, str):
                # If it is just a string, simply assign the new value to this key
                info[remap] = remap_input
            else:
                raise ValueError("Unknown remapping specified.")

        elif keep_unknown_keys:
            if replace_char_with_underscores:
                remap_key = remap_key.replace(replace_char_with_underscores, "_")
            info[remap_key] = remap_input

    @staticmethod
    def remap_dict(
        input_dictionary, remapping_dict, keep_unknown_keys=False, replace_char_with_underscores=None
    ):
        """Given an input dictionary and a remapping dictionary, return the remapped dictionary
        :param input_dictionary: Input dictionary
        :type input_dictionary: dict
        :param remapping_dict: Dictionary of Remapper objects
        :type remapping_dict: dict
        :param keep_unknown_keys: If no remapping is found, keep the data
            with its original key and value. Defaults to False
        :type keep_unknown_keys: bool, optional
        :param replace_char_with_underscores: If no remapping is found,
            replace a character in the key with underscores. Defaults to None
        :type replace_char_with_underscores: str, optional
        :return: Remapped dictionary
        :rtype: dict
        """

        info = {}
        for key in input_dictionary:
            Remapper.remap(
                info,
                remapping_dict,
                key,
                input_dictionary[key],
                keep_unknown_keys=keep_unknown_keys,
                replace_char_with_underscores=replace_char_with_underscores,
            )
        return info
