import salmon.lang as sal
from salmon.comp import dagonly
from salmon.codegen import spark, viz
from salmon.utils import *


@dagonly
def protocol():

    cols_concatenated_DFs = [
        defCol("store_code_uc", "INTEGER", [1]),
        defCol('upc', 'INTEGER', [1]),
        defCol('week_end', 'INTEGER', [1]),
        defCol('q', 'INTEGER', [1]),
        defCol('avg_unit_p', 'FLOAT', [1])
    ]

    cols_temp_UPC_brandBU_crspnd = [
        defCol('brand_code_bu', 'FLOAT', [2]),
        defCol('brand_descr_bu', 'STRING', [2]),
        defCol('upc', 'INTEGER', [2]),
        defCol('size1_amount', 'FLOAT', [2]),
    ]

    # concatenated DFs from local_workflow.py
    concatenated_DFs = sal.create('concatenated_DFs', cols_concatenated_DFs, set([1]))

    # the output of preprocess_products.py
    temp_UPC_brandBU_crspnd = sal.create('temp_UPC_brandBU_crspnd', cols_temp_UPC_brandBU_crspnd, set([1]))

    '''
    SECTION 1
    Compute the quantity weighted average price per unit
    & total quantity sold at the store-brand level
    '''
    w_upc = sal.join(concatenated_DFs, temp_UPC_brandBU_crspnd, 'w_upc', ['upc'], ['upc'])
    w_avg_OZ_p = sal.divide(w_upc, 'w_avg_OZ_p', 'avg_OZ_p', ['avg_unit_p', 'size1_amount'])
    w_q_upd = sal.multiply(w_avg_OZ_p, 'w_q_upd', 'q', ['q', 'size1_amount'])
    brand_OZq_sum = sal.aggregate(w_q_upd, 'brand_OZq_sum', ['store_code_uc', 'brand_code_bu', 'week_end'],
                                  'q', '+', 'brand_OZq')
    total_brnd_OZq = sal.join(w_q_upd, brand_OZq_sum, 'total_brnd_OZq', ['store_code_uc', 'brand_code_bu', 'week_end'],
                              ['store_code_uc', 'brand_code_bu', 'week_end'])
    w_wghtd_OZ_brnd_p = sal.multiply(total_brnd_OZq, 'w_wghtd_OZ_brnd_p', 'wghtd_OZ_brnd_p', ['q', 'avg_OZ_p'])
    w_wghtd_OZ_brnd_p_final = sal.divide(w_wghtd_OZ_brnd_p, 'w_wghtd_OZ_brnd_p_final', 'wghtd_OZ_brnd_p',
                                         ['wghtd_OZ_brnd_p', 'brand_OZq'])
    brnd_p_sum = sal.aggregate(w_wghtd_OZ_brnd_p_final, 'brnd_p_sum', ['store_code_uc', 'brand_code_bu', 'week_end'],
                               'wghtd_OZ_brnd_p', '+', 'avg_OZ_brnd_p')
    result = sal.join(brnd_p_sum, w_wghtd_OZ_brnd_p_final, 'result', ['store_code_uc', 'brand_code_bu', 'week_end'],
                      ['store_code_uc', 'brand_code_bu', 'week_end'])
    final_result = sal.project(result, 'final_result', ["avg_OZ_brnd_p", "week_end","store_code_uc", "brand_code_bu",
                                                        "brand_descr_bu", "brand_OZq"])

    '''
    SECTION 2
    Compute the average price per OZ & total OZs sold for each brand at the
    retailer-$geo_unit level, by compiling the store level data that comprises each
    retailer-$geo_unit. Compute the total quantity sold by each retailer-$geo_unit
    '''

    # TODO: rewrite to use nested binary joins
    temp_sum = sal.aggregate(final_result, 'temp_sum', ['zip3', 'rtlr', 'brand_code_bu', 'week_end'], 'brand_OZq', '+', 'brand_OZq')
    result_brnd_sum = sal.join(final_result, temp_sum, 'result_brnd_sum', ['zip3', 'rtlr', 'brand_code_bu', 'week_end'], \
                               ['zip3', 'rtlr', 'brand_code_bu', 'week_end'])
    wghtd_p_mult = sal.multiply(result_brnd_sum, 'wghtd_p_mult', 'wghtd_p', ['brand_OZq', 'avg_OZ_brnd_p'])
    wghtd_p_final = sal.divide(wghtd_p_mult, 'wghtd_p_final', 'wghtd_p', ['wghtd_p', 'q'])
    wghtd_p_sum = sal.aggregate(wghtd_p_final, 'wghtd_p_sum', ['zip3', 'rtlr', 'brand_code_bu', 'week_end'], 'wghtd_p', '+', 'p')
    # TODO: rewrite to use nested binary joins
    sec_4_result = sal.join(wghtd_p_final, wghtd_p_sum, 'sec_4_result', ['zip3', 'rtlr', 'brand_code_bu', 'week_end'], \
                            ['zip3', 'rtlr', 'brand_code_bu', 'week_end'])

    # TODO: filter out sec_4_result rows where 'zip3' cell is null

    final = sal.project(sec_4_result, 'final', ['zip3', 'rtlr', 'week_end', 'brand_code_bu', 'q', 'p'])

    opened = sal.collect(final, 1)

    return set([concatenated_DFs, temp_UPC_brandBU_crspnd])

if __name__ == "__main__":

    dag = protocol()

    viz = viz.VizCodeGen(dag)
    viz.generate("nielsen_workflow", "/tmp")

    cg = spark.SparkCodeGen(dag)
    cg.generate("nielsen_workflow", "/tmp")

    print("Spark code generated in /tmp/nielsen_workflow.py")
