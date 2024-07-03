from enum import Enum, auto

default_config = {
    'elif/else if': 'elif',         # Whether to use "else if" or "elif" for conditionals
    'indent': '\t',                 # Character (or str) that will be used to indent
    'indent_depth': 0,              # How many indents to start with
    'indent_section_body': False,   # Whether to indent the body of sections or not
    'indent_condition_body': True,  # Whether to indent the body of conditionals or not
    'section_separator': '\n',      # Character (or str) that will be inserted between sections
    'group_separator': '\n',        # Multiple sections can be grouped together.
                                    # This is the character (or str) that will separate them
    # 'group_separator': '\n; {} ;\n; {} ;\n\n'.format('-'*70, '-'*70)
    'skip_comments': False,         # Whether to include commands starting with ";" in the output build
}


class SectionType(Enum):
    Key = auto()
    Present = auto()
    Resource = auto()
    Constants = auto()
    CommandList = auto()
    CustomShader = auto()
    ShaderOverride = auto()
    TextureOverride = auto()
    ShaderRegex = auto()

    def __str__(self):
        return self.name

    def __repr__(self):
        return repr(self.name)

section_hash_length = {
    SectionType.TextureOverride: 8,
    SectionType.ShaderOverride: 12
}
def get_section_hash_length(section_type: SectionType):
    if section_type in section_hash_length:
        return section_hash_length[section_type]
    return 0


class IniCommandBuilder():
    def __init__(self):
        self.commands = []

    def add_command(self, command):
        '''
            Adds command as is and **returns it**.
            Newlines are inserted automatically.\n
            Accepts conditional commands.
        '''
        if type(command) is not str and not isinstance(command, IniSectionConditional):
            raise Exception('Invalid command passed')
         
        self.commands.append(command)
        return command

    def add_comment(self, comment):
        '''
            Adds comment as is and **returns it**.
            Newlines are inserted automatically.
        '''
        return self.add_command(f'; {comment}')

    def add_persistent_comment(self, comment):
        '''
            Adds comment that will persist through comments skipping and **returns it**.
            Newlines are inserted automatically.
        '''
        return self.add_command(f'+; {comment}')

    def add_commands(self, commands):
        '''
            Adds multiple commands as is.
            Newlines are inserted automatically.\n
            Accepts conditional commands.
        '''
        self.commands.extend(commands)

    def check_texture_override(self, slot: str):
        '''
            Adds `checktextureoverride = **slot**`
        '''
        command = 'checktextureoverride = {}'.format(slot)
        self.add_command(command)

    def add_override(self, slot: str, resource: str, ref=False, copy=False):
        '''
            Adds `slot = [ref/copy/] resource`\n
            This is harder to read than a simple add_command('vb2 = ref ResourceWhatever')
            but add_command is slightly more error prone
        '''
        if ref and copy:
            raise Exception('Cannot override resource with `ref` and `copy` at the same time')

        command = '{} = {}{}'.format(
            slot,
            'ref ' if ref else ('copy ' if copy else ''),
            resource
        )
        self.add_command(command)
    
    def build(self, config=default_config) -> str:
        '''
            Builds and returns the string with all commands
            in the order that they have been added in. Adds
            separators and indentations according to config.
        '''
        s = ''
        for command in self.commands:
            if type(command) is str:
                if config['skip_comments']:
                    if command.startswith(';'):
                        continue
                if command.startswith('+;'):
                    command = command.replace('+;', ';')
                s += '{}{}\n'.format(
                    config['indent'] * config['indent_depth'],
                    command
                )
            elif isinstance(command, IniSectionConditional):
                s += command.build(config)
            else:
                raise Exception('Invalid Command', command)
        
        return s
    
    # Being able to directly print(IniCommandBuilder) is nice
    def __str__(self):
        return self.build()


class IniSectionConditional():
    def __init__(self):
        self.if_condition    :str = ''
        self.else_condition  :str = ''
        self.elif_conditions :list[str] = []

        self.condition_commands = {
            # condition<str>: commands<IniCommandBuilder>
            # ...
            # Duplicate conditions disallowed at the same depth
            # However, its possible to have the same conditions
            # **at different depths** (nested if/else statements)
        }

        # I could include this in self.condition_commands instead but an else clause
        # has no condition obviously, so I'd have to give it a dummy key, which
        # introduces an extremely small chance it'll conflict with a real key...
        self.else_commands: IniCommandBuilder
    
    def add_if_clause(self, condition) -> IniCommandBuilder:
        if condition in self.condition_commands:
            raise Exception('Condition already exists')
        
        self.if_condition = condition
        self.condition_commands[self.if_condition] = IniCommandBuilder()
        return self.condition_commands[condition]

    def add_elif_clause(self, condition) -> IniCommandBuilder:
        if condition in self.condition_commands:
            raise Exception('Condition already exists')

        self.elif_conditions.append(condition)
        self.condition_commands[condition] = IniCommandBuilder()
        return self.condition_commands[condition]

    def add_else_clause(self) -> IniCommandBuilder:

        # value used here doesnt matter as long as it doesnt evaluate to false 
        self.else_condition = '1'

        self.else_commands = IniCommandBuilder()
        return self.else_commands

    def get_condition_commands(self, condition) -> IniCommandBuilder:
        return self.condition_commands[condition]

    def build(self, config):
        if not self.if_condition:
            raise Exception('Missing if condition')

        indent = config['indent'] * config['indent_depth']
        body_config = {
            **config,
            'indent_depth': (
                config['indent_depth'] + 1
                if config['indent_condition_body']
                else config['indent_depth']
            )
        }

        s  = '{}if {}\n'.format(indent, self.if_condition)
        s += self.condition_commands[self.if_condition].build(body_config)

        if len(self.elif_conditions) > 0:
            for elif_condition in self.elif_conditions:
                s += '{}{} {}\n'.format(indent, config['elif/else if'], elif_condition)
                s += self.condition_commands[elif_condition].build(body_config)

        if self.else_condition:
            s += '{}else\n'.format(indent)
            s += self.else_commands.build(body_config)

        s += '{}endif\n'.format(indent)

        return s
    
    def __str__(self):
        return self.build()


class IniSection():
    def __init__(self, name, section_type: SectionType, hash:str=None, comment:str=None):
    
        # Validate assumptions about parameters
        if not isinstance(section_type, SectionType):
            raise Exception('`type` must be an instance of SectionType enum')
        
        required_hash_length = get_section_hash_length(section_type)
        if required_hash_length > 0:
            # Check hash passed
            if not hash:
                raise Exception('Hash required for section of type {}'.format(section_type))
            
            if type(hash) is not str:
                raise Exception('Hash passed must be a string not {}'.format(type(hash)))

            # Check that the hash passed is a valid hex string
            try: int(hash, 16)
            except:
                raise Exception('Invalid hash passed: {}'.format(hash))
            
            # Check hash length matches specs
            if len(hash) != required_hash_length:
                raise Exception('Expected hash length to be {} but got {} instead.'.format(required_hash_length, len(hash)))

        elif hash:
            raise Exception('Useless hash passed for section of type {}'.format(section_type))

        self.comment = comment
        self.name = name
        self.section_type = section_type
        self.body = IniCommandBuilder()
        
        if hash:
            self.body.add_command('hash = {}'.format(hash))

    def get_section_title(self):
        return '{}{}'.format(self.section_type, self.name)

    def build(self, config=default_config):
        indent_depth = config['indent_depth']

        s = ''

        # Section Comment
        if self.comment and not config['skip_comments']:
            s += '{}; {}\n'.format(
                config['indent'] * indent_depth,
                self.comment
            )

        # Section Title
        s += '{}[{}]\n'.format(
            config['indent'] * indent_depth,
            self.get_section_title()
        )

        # Section Body
        if config['indent_section_body']:
            indent_depth += 1

        s += self.body.build({
            **config,
            'indent_depth': indent_depth
        })

        return s

    def __str__(self):
        return self.build()




class IniBuilder():

    def __init__(self, config={}):
        '''
        Config will be validated:
        ```
        config: {
            'elif/else if':          ('choice', ['elif', 'else if']),
            'indent':                ('str',),
            'indent_depth':          ('int',),
            'indent_section_body':   ('bool',),
            'indent_condition_body': ('bool',),
            'section_separator':     ('str',),
            'group_separator':     ('str',),
        }
        ```
        '''
        # Uses the default config key/value pairs to populate the config.
        # i.e. the user doesn't have to provide custom values for all the
        # config keys.
        # For example, IniBuilder(config={'indent': ' '*4})
        # is valid and would use the default config values except for
        # the indent key which its value is replaced by 4 space characters
        config = {
            **default_config,
            **config
        }

        # Making it clear that this method is expected to raise exceptions if
        # the config is invalid. Otherwise, execution continues
        try: self.validate_config(config)
        except Exception as X: raise X

        # Config validation checks passed
        self._config = config

        # As of python 3.7, dicts being insert ordered is officially guaranteed
        # and can be relied on (and unofficially since python 3.6)
        self._sections = {
            # section_title<str>: (
            #       section<IniSection>,
            #       group<int>
            # ),
            # ...
        }

        self.header = ''
        self.footer = ''
        self._namespace = ''
        self._group_deco = {
            # group<int>: (
            #   header<str>,
            #   footer<str>,
            # ),
            # ...
        }

    def set_group_header(self, group, header):
        if group not in self._group_deco:
            self._group_deco[group] = ('', '')

        self._group_deco[group] = (header, self._group_deco[group][1])

    def set_group_footer(self, group, footer):
        if group not in self._group_deco:
            self._group_deco[group] = ('', '')

        self._group_deco[group] = (self._group_deco[group][0], footer)


    def add_section(self, ini_section: IniSection, group: int = 0, force=False):
        '''
            Sections with the same group value will appear in the
            built string in the order that they were added in.
            The sections with the higher group value will appear after
            the sections with lower group values and vice versa.
            \n
            For example, I can add:
            - TextureOverride sections with a group of 0
            - CommandList sections with a group of 1
            - Resource sections with a group of 2
            \n
            in order to have them appear in this order 
            `TextureOverride -> CommandList -> Resource`
            in the built string without being forced to add them to the 
            ini in that same order
            \n
            Set `force=True` to add the section even if a section with the same 
            section title has been added previously. The forcibly added section will
            replace the existing section.
        '''
        section_title = ini_section.get_section_title()
        if not force and section_title in self._sections:
            raise Exception(f'{section_title} already exists')
        
        self._sections[section_title] = (
            ini_section,
            group
        )

        return section_title
    
    def get_section(self, section_title) -> IniSection:
        return self.__getitem__(section_title)

    def set_namespace(self, value: str):
        '''
        Adds to the very start of the ini, and before the header,
        `
        namespace = value\\n\\n
        `
        '''
        self._namespace = 'namespace = {}\n\n'.format(value)

    def set_section_group(self, section_title, group):
        if section_title not in self._sections:
            raise Exception('Section with section_title ({}) does not exist within ini'.format(section_title))
        self._sections[section_title][1] = group

    def build(self):
        '''
            Build groups of the ini one at a time and then joins them to form the full ini.
            Each group is formed from, the sections with the same group value, and the order 
            of each section **within its group** depends on the order it was added to the ini in.
        '''
        ini_groups = {
            # group<int>: partial_ini<str>
        }

        for i, section_title in enumerate(self._sections):
            section  = self._sections[section_title][0]
            group = self._sections[section_title][1]

            if group not in ini_groups:
                ini_groups[group] = ''
            else:
                ini_groups[group] += self._config['section_separator']

            ini_groups[group] += section.build(self._config)


        # Join the groups according to their sorted values to build the full ini
        full_ini = self._namespace + self.header
        for i, group in enumerate(sorted(ini_groups.keys())):
            if group in self._group_deco:
                group_header, group_footer = self._group_deco[group]
            else:
                group_header = group_footer = ''
            
            full_ini += group_header
            
            full_ini += ini_groups[group]

            if i < len(ini_groups.keys()) - 1:
                full_ini += self._config['group_separator']

            full_ini += group_footer

        full_ini += self.footer
        
        return full_ini
    
    @classmethod
    def validate_config(cls, config):
        '''
            Basic validation for config  
        '''
        config_validate = {
            'elif/else if':          ('choice', ['elif', 'else if']),
            'indent':                ('str',),
            'indent_depth':          ('int',),
            'indent_section_body':   ('bool',),
            'indent_condition_body': ('bool',),
            'section_separator':     ('str',),
            'group_separator':       ('str',),
            'skip_comments':         ('bool',),
        }

        for key, value in config.items():
            if key not in config_validate:
                raise Exception('Config: Unknown key: {}'.format(key))
            
            value_type = config_validate[key][0]
            if value_type == 'choice':
                options = config_validate[key][1]
                if value not in options:
                    raise Exception('Config: Invalid value for {}. Valid values are {}'.format(key, options))
            elif value_type == 'str':
                if type(value) is not str:
                    raise Exception('Config: Expected string value for {} key. Got {} ({})'.format(key, value, type(value)))
            elif value_type == 'int':
                if type(value) is not int:
                    raise Exception('Config: Expected integer value for {} key. Got {} ({})'.format(key, value, type(value)))
            elif value_type == 'bool':
                if type(value) is not bool:
                    raise Exception('Config: Expected boolean value for {} key. Got {} ({})'.format(key, value, type(value)))
            else:
                raise Exception('Programming Error', value_type)
    
    def __str__(self):
        return self.build()
    
    def __getitem__(self, section_title) -> IniSection:
        return self._sections[section_title][0]
