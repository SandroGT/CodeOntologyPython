import owlready2 as owl

from codeontology.test.utils import do_query_and_show_res


ontology_file_path = r"C:\Users\sandr\codeontology\output\Sphinx-5.2.3.owl"
ontology = owl.get_ontology(str(ontology_file_path))
namespace = ontology.load()

query = """
prefix woc: <http://rdf.webofcode.org/woc/>

SELECT DISTINCT ?s ?c
WHERE {
    ?s a woc:Class .
    ?s woc:hasConstructor ?c
}
"""

do_query_and_show_res(query)
