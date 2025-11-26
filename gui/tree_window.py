def refresh_opened_bases(self):
    folder_item = self.opened_bases_builder.build_tree()
    if folder_item:
        index = self.tree.model().indexFromItem(folder_item)
        self.tree.setFirstColumnSpanned(index.row(), index.parent(), True)
