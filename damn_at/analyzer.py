"""
Role
====
Analyzer convience class to find the right plugin for a mimetype
and address it.
"""
import os
import sys
import pwd
import grp
import time

from metrology.instruments.gauge import Gauge

from damn_at import registry, MetaDataValue, MetaDataType
from damn_at.pluginmanager import DAMNPluginManagerSingleton
from damn_at.utilities import is_existing_file, calculate_hash_for_file, get_referenced_file_ids, abspath
from damn_at.metadatastore import MetaDataStore

from damn_at import mimetypes


class AnalyzerException(Exception):
    """Base Analyzer Exception"""
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg
    def __str__(self):
        return repr(self.msg)


class AnalyzerFileException(AnalyzerException):
    """Something wrong with the file"""
    pass
  

class AnalyzerUnknownTypeException(AnalyzerException):
    """Unknown type"""
    pass


class AnalyzerGauge(Gauge):
    """Gauge that returns the number of analyzer-plugins"""
    def __init__(self, analyzer):
        self.analyzer = analyzer
    def value(self):
        return len(self.analyzer.analyzers)


class Analyzer(object):
    """
    Analyze files and tries to find known assets types in it.
    """
    def __init__(self):
        registry.gauge('damn_at.analyzer.number_of_analyzers', AnalyzerGauge(self))
        self.analyzers = {}
        plugin_mgr = DAMNPluginManagerSingleton.get()

        for plugin in plugin_mgr.getPluginsOfCategory('Analyzer'):
            if plugin.plugin_object.is_activated:
                for mimetype in plugin.plugin_object.handled_types:
                    self.analyzers[mimetype] = plugin.plugin_object
    
    def get_supported_mimetypes(self):
        """Returns a list of supported mimetypes, 'handled_types' of all analyzers
        
        :rtype: list<string>
        """
        return self.analyzers.keys()
        
    def _file_metadata(self, an_uri, file_descr):
        stat = os.stat(an_uri)
        if file_descr.metadata is None:
            file_descr.metadata = {}
        file_descr.metadata['pw_name'] = MetaDataValue(type=MetaDataType.STRING, string_value=pwd.getpwuid(stat.st_uid).pw_name)
        file_descr.metadata['gr_name'] = MetaDataValue(type=MetaDataType.STRING, string_value=grp.getgrgid(stat.st_gid).gr_name)
        file_descr.metadata['st_size'] = MetaDataValue(type=MetaDataType.INT, int_value=stat.st_size)
        
        file_descr.metadata['st_ctime'] = MetaDataValue(type=MetaDataType.STRING, string_value=time.asctime(time.localtime(stat.st_ctime)))
        file_descr.metadata['st_mtime'] = MetaDataValue(type=MetaDataType.STRING, string_value=time.asctime(time.localtime(stat.st_mtime)))
        
        #TODO:
        try:
            from repository import Repository
            repo = Repository('/home/ayush/GSOC14/damn-at/damn-test-files')
            
            repo.get_meta_data(an_uri, file_descr)
        except Exception as e:
          print(e)
          
    def analyze_file(self, an_uri):
        """Returns a FileDescription
        
        :param an_uri: the URI pointing to the file to be analyzed
        :rtype: :py:class:`damn_at.FileDescription`
        :raises: AnalyzerException, AnalyzerFileException, AnalyzerUnknownTypeException
        """
        if not is_existing_file(an_uri):
            raise AnalyzerFileException('E: Analyzer: No such file "%s"!'%(an_uri))
        mimetype = mimetypes.guess_type(an_uri, False)[0]
        if mimetype in self.analyzers:
            file_descr = self.analyzers[mimetype].analyze(an_uri)
            file_descr.mimetype = mimetype
            self._file_metadata(an_uri, file_descr)
            #print file_descr
            return file_descr
        else:
            raise AnalyzerUnknownTypeException("E: Analyzer: No analyzer for %s (file: %s)"%(mimetype, an_uri))


def analyze(a, m, file_name):
    """TODO: move hashing to generic function and metadatastore usage to the metadatastore module. """
    def hash_file_descr(file_descr):
        CACHE = {}
        def cached_calculate_hash_for_file(file_name):
            if file_name not in CACHE:
                path = abspath(file_name, file_descr)
                CACHE[file_name] = calculate_hash_for_file(path)
            return CACHE[file_name]
        file_ids = get_referenced_file_ids(file_descr)
        for file_id in file_ids:
            file_id.hash = cached_calculate_hash_for_file(file_id.filename)
        
    def analyze_file(file_name, file_descr=None):
        file_name = abspath(file_name, file_descr)

        hashid = calculate_hash_for_file(file_name)
        #print "HASH "+hashid
        if m.is_in_store('/tmp/damn', hashid):
            print('Fetching from store...%s'%(hashid))
            descr = m.get_metadata('/tmp/damn', hashid)
            return descr, True
        else:
            print(a.get_supported_mimetypes())
            print('Analyzing...')
            descr = a.analyze_file(file_name)
            hash_file_descr(descr)
            m.write_metadata('/tmp/damn', hashid, descr)
            return descr, False
    
    descr, from_store = analyze_file(file_name)
    if descr.assets:
        print('Assets: %d'%len(descr.assets))
        for asset in descr.assets:
            print('  -->%s  (%s)'%(asset.asset.subname, asset.asset.mimetype))

    file_ids = get_referenced_file_ids(descr)
    paths = set([x.filename for x in file_ids])
    for path in paths:
        if path != file_name:
            #print('Analyzing', path, file_name)
            try:
                _, from_store = analyze_file(path, descr)
                #print(_)
            except AnalyzerUnknownTypeException as e:
                print(e)

def main():
    import logging
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    
    store_path = sys.argv[1]
    file_name = sys.argv[2]
    print('-'*70)
    print('Analyzing %s into %s'%(file_name, store_path))
    print('-'*70)
    a = Analyzer()
    m = MetaDataStore(store_path)
    
    if os.path.isfile(file_name):
        analyze(a, m, os.path.abspath(file_name))
    else:
        for root, dirs, files in os.walk(file_name):
            if '.git' in dirs:
                dirs.remove('.git')
            for f in files:
                if not f.startswith('.'):
                    try:
                        analyze(a, m, os.path.join(root, f))
                    except AnalyzerUnknownTypeException as e:
                        print(e)
    
    

if __name__ == '__main__': 
    main()
