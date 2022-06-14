import coopstorage.eventDefinition as cevents

class LocationNotInStorageException(Exception):
    def __init__(self, storage_state):
        cevents.raise_event_LocationNotInStorageException(cevents.OnLocationNotInStorageExceptionEventArgs(
            storage_state=storage_state
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class NoLocationFoundException(Exception):
    def __init__(self, storage_state):
        cevents.raise_event_NoLocationFoundException(cevents.OnNoLocationFoundExceptionEventArgs(
            storage_state=storage_state
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class NoLocationWithCapacityException(Exception):
    def __init__(self, content, resource_uom_space, loc_uom_space_avail, loc_states, storage_state):
        cevents.raise_event_NoLocationWithCapacityException(cevents.OnNoLocationWithCapacityExceptionEventArgs(
            content=content,
            resource_uom_space=resource_uom_space,
            loc_uom_space_avail=loc_uom_space_avail,
            loc_states=loc_states,
            storage_state=storage_state
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class ContentDoesntMatchLocationException(Exception):
    def __init__(self, location, content):
        cevents.raise_event(event=cevents.ProductionEventType.EXCEPTION_CONTENT_DOESNT_MATCH_LOCATION,
                            args=cevents.OnContentDoesntMatchLocationExceptionEventArgs(
                                location=location,
                                content=content
                            )
        )
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class ContentDoesntMatchLocationActiveDesignationException(Exception):
    def __init__(self, content, loc_inv):
        cevents.raise_event_ContentDoesntMatchLocationDesignationException(cevents.OnContentDoesntMatchLocationActiveDesignationExceptionEventArgs(
            content=content,
            loc_inv=loc_inv
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class NoRoomAtLocationException(Exception):
    def __init__(self, loc_inv):
        cevents.raise_event_NoRoomAtLocationException(cevents.OnNoRoomAtLocationExceptionEventArgs(
            loc_inv=loc_inv
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class MissingContentException(Exception):
    def __init__(self, loc_inv):
        cevents.raise_event_MissingContentException(cevents.OnMissingContentExceptionEventArgs(
            loc_inv=loc_inv
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__}"

class NoLocationToRemoveContentException(Exception):
    def __init__(self, content, storage_state):
        self.content=content
        self.storage_state = storage_state
        cevents.raise_event_NoLocationToRemoveContentException(cevents.OnNoLocationToRemoveContentExceptionEventArgs(
            content=content,
            storage_state=storage_state
        ))
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__} content: {self.content}"

class ResourceUoMNotInManifestException(Exception):
    def __init__(self, resourceUoM, manifest):
        self.resourceUoM = resourceUoM
        self.manifest = manifest
        super().__init__(str(self))

    def __str__(self):
        return f"{type(self).__name__} {self.resourceUoM} not in manifest: {self.manifest}"