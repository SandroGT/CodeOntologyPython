import owlready2 as owl

from codeontology.test.utils import do_query_and_show_res


ontology_file_path = r"C:\Users\sandr\codeontology\output\okgraph-0.0.1.nt"
ontology = owl.get_ontology(str(ontology_file_path))
namespace = ontology.load()

query = """
prefix woc: <http://rdf.webofcode.org/woc/>

SELECT DISTINCT ?s
WHERE {
    ?s a woc:ImportStatement .
}
"""

do_query_and_show_res(query)
