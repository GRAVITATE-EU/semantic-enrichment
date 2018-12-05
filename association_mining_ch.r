# Association mining of CH item sets to create rules that can infer semantic_type(...)

# Installation requires
#	install.packages( "arules", dependencies = TRUE )

library(arules)

# check args
args = commandArgs( trailingOnly=TRUE )
if (length(args) != 2) {
	stop( "two arguments expected", call.=FALSE )
}

tdata <- read.transactions(
	file = args[1],
	format = "basket",
	sep="\t",
	rm.duplicates = FALSE,
	encoding = "UTF-8"
	)

# supp and conf parameters are the minimum allowed values (find this emprically by looking at the rules sets)
# maxlen = max number of item sets in a rule (default 10)
# maxtime = max time in seconds to check a subset (default 5)
# supp = min support. if this is too low the subsets get very large, memory footprint grows a lot, and it takes a very long time to complete (default 0.1)
# conf = min confidence. if this is too low rules will be reported that are very poor (default 0.8)
# see https://www.rdocumentation.org/packages/arules/versions/1.6-1/topics/ASparameter-classes
rules <- apriori (
	data = tdata,
	parameter = list( supp = 0.005, conf = 1.0, maxlen=5, maxtime=20 )
	)

# OLD parameter = list( supp = 0.1, conf = 1.0, maxlen=5, maxtime=20 )


# %pin% is essentially regex
rules_rel_subset <- subset(
	x = rules,
	subset = rhs %pin% "semantic_type[(]"
	)

rules_rel_subset_conf <- sort (
	rules_rel_subset,
	by="confidence",
	decreasing=TRUE
	)

write(
	x = rules_rel_subset_conf,
	file = args[2],
	sep = "\t"
	)

