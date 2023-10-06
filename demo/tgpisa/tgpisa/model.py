from turbogears.database import PackageHub

# import some basic SQLObject classes for declaring the data model
# (see http://www.sqlobject.org/SQLObject.html#declaring-the-class)
# import some datatypes for table columns from SQLObject
# (see http://www.sqlobject.org/SQLObject.html#column-types for more)

__connection__ = hub = PackageHub("tgpisa")


# your data model


# class YourDataClass(SQLObject):
#     pass
