import shapefile
 
nomSortie = input()

w = shapefile.Writer(nomSortie)

w.close()
