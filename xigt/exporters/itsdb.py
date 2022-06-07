import logging
from os.path import isfile, join as pjoin
from os import environ

try:
    from delphin import tsdb
except ImportError:
    raise ImportError(
        'Could not import pyDelphin module. Get it from here:\n'
        '  https://github.com/goodmami/pydelphin'
    )


# ECC 2021-07-26: the lambda for i-comment assumes there will be a translation, but it's not always present,
# so this is a helper function for the lambda to use
def build_comment(igt):
    comment = " ".join(item.get_content() for item in next(igt.select(type="glosses"), []))

    try:
        comment += " // " + str(next(igt.select(type="translations"), [""])[0].get_content())
        return comment
    except:
        return comment



# EMB 2019-04-05 Previously, the lamba part was in prepare_config, but in that case, the last mapper was used for all keys, and I couldn't figure out why. Nor could I see why the lambas weren't called right away. Moving that into DEFAULT_CELLS solved the problem, so I could hae both i-input and i-comment filled in.

DEFAULT_CELLS = [
    # i-input is a string of either the first phrase (preferred) or all words
    #('i-input', lambda igt: eval('next(igt.select(type="phrases"), [""])[0].value() or '
    # '" ".join(item.get_content() '
    # '         for item in next(igt.select(type="words"),[]))')),
    # KPH 2019-09-30 The first phrases tier is not preferred if we want to target the morpheme segmented line. If the data was converted from flex
    # the first phrase tier with id="l" is the language line. We want the phrase tier with id="p"
    ('i-input', lambda igt: eval('next(igt.select(id="p"), [""])[0].value() or '
    'next(igt.select(type="phrases"), [""])[0].value() or '
     '" ".join(item.get_content() '
     '         for item in next(igt.select(type="words"),[]))')),
    # i-comment is the glosses concatenated, followed by the translation
    ('i-comment', lambda igt: build_comment(igt)),
    ('i-wf', lambda igt: eval('0 if igt.get_meta("judgment") else 1')),
]

def xigt_export(xc, outpath, config=None):
    config = prepare_config(config)
    if not config.get('relations') or not isfile(config['relations']):
        logging.error('Relations file required for [incr tsdb()] export.')
        return

    # ECC 2021-07-26: fix to work with new version of pydelphin
    # read in the schema, export the corpus, initialize the db, and write it in an item file
    config['schema'] = tsdb.read_schema(config['relations'])
    items = export_corpus(xc, config)
    tsdb.initialize_database(outpath, config['schema'], files=False)
    tsdb.write(outpath, 'item', items)

def prepare_config(config):
    if config is None:
        config = {}
    config.setdefault('i-id_start', 0)
    config.setdefault('i-id_skip', 10)
    # attempt to find default Relations file
    if 'relations' not in config and 'LOGONROOT' in environ:
        rel_path = pjoin(
            environ['LOGONROOT'],
            'lingo/lkb/src/tsdb/skeletons/english/Relations'
        )
        if isfile(rel_path):
            logging.info('Attempting to get relations file from {}'
                         .format(rel_path))
            config['relations'] = rel_path
    config['cells'] = DEFAULT_CELLS
    return config

def export_corpus(xc, config):
    id_start = config['i-id_start']
    id_skip = config['i-id_skip']
    items = []
    for i, igt in enumerate(xc):
        config['__i-id_current__'] = id_start + (i * id_skip)
        logging.debug('Exporting {}'.format(str(igt.id)))
        # make a list of tsdb records
        items.append(tsdb.make_record(export_igt(igt, config), config['schema']['item']))
    return items

def export_igt(igt, config):
    row = {'i-id': config['__i-id_current__']}
    for cell_map in config['cells']:
        key, mapper = cell_map
        try:
            row[key] = mapper(igt)
        except SyntaxError:
            logging.error('Malformed cell mapper expression for {}'
                          .format(key))
            raise
        row['i-length'] = len(row['i-input'].split())
    return row