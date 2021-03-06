import os
import logging
import numpy as np
import pandas as pd

from networkx import Graph
from operator import itemgetter
from typing   import List, Sequence, Tuple

import invisible_cities.core.system_of_units as units

from invisible_cities.reco.paolina_functions  import length as track_length


logger = logging.getLogger('FanalAna')


def get_new_energies(event_voxels : pd.DataFrame) -> List[float]:
    """
    It redistributes the energy of negligible voxels.
    As a first approach, we give the energy of negligible voxels to
    the closest non-negligible voxel.

    Parameters
    ----------
    event_voxels : pd.DataFrame
      Containing the voxels of an event.

    Returns
    -------
    A List with the new energies of all the incoming voxels
    """

    # Identify voxels with low energy
    negl_voxels = event_voxels[event_voxels.negli == True]

    negl_neig_pairs = []
    neig_index = []

    for i, negl_voxel in negl_voxels.iterrows():
        # looking the closest neighbour of every negligible voxel
        min_dist = 1000
        closest_index = i
        for j, event_voxel in event_voxels.iterrows():
            if ((i != j) & (j not in negl_voxels.index)):
                dist = np.sqrt((negl_voxel.X-event_voxel.X)**2 +
                               (negl_voxel.Y-event_voxel.Y)**2 +
                               (negl_voxel.Z-event_voxel.Z)**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_index = j

        negl_neig_pairs.append((i, closest_index))
        neig_index.append(closest_index)

        logger.debug('    Negl. Voxel Id: {0} with E: {1:4.1f} keV  -->  Voxel Id: {2} '
                     .format(i, negl_voxel.E / units.keV, closest_index))

    # Generating the list of new energies
    new_energies = []
    for i, event_voxel in event_voxels.iterrows():
        # if negligible voxel -> new energy = 0
        if i in negl_voxels.index:
            new_energies.append(0.)
        # if voxel is the closest neigh. of any voxel ->
        # new energy = old_energy + negligibles
        elif i in neig_index:
            new_voxelE = event_voxel.E
            extraE = sum(event_voxels.loc[pair[0]].E for pair in negl_neig_pairs \
                     if i == pair[1])
            new_energies.append(new_voxelE + extraE)
        # The rest of voxels maintain their energies
        else:
            new_energies.append(event_voxel.E)

    return new_energies



def get_voxel_track_relations(event_voxels : pd.DataFrame,
                              event_tracks : Sequence[Graph]
                             ) -> List[int]:
    """
    It makes the association between voxels, and the track they belong to.

    Parameters
    ----------
    event_voxels : pd.DataFrame
      Containing the voxels of an event.
    event_tracks : Sequence[Graph]
      Containing the tracks of an event.

    Returns
    -------
    A list with the track id each voxel belongs to.
    """
    voxel_tracks = []
    for i, event_voxel in event_voxels.iterrows():
        if not event_voxel.negli:
            found = False
            voxel_pos = (event_voxel.X, event_voxel.Y, event_voxel.Z)
            # Look into each track
            for j in range(len(event_tracks)):
                for node in event_tracks[j].nodes():
                    node_pos = (node.X, node.Y, node.Z)
                    # If voxel in this track, append trackId and break
                    if voxel_pos == node_pos:
                        found = True
                        voxel_tracks.append(j)
                        break
                if found: break

        else:
            voxel_tracks.append(np.nan)

    return voxel_tracks



def process_tracks(event_tracks : Sequence[Graph],
                   track_Eth    : float
                  ) -> List[Tuple[float, float, Graph]]:
    """
    It calculates tracks energies.
    It filters tracks with length smaller than 2 times the blob_radius.
    It filters tracks with energy lower than threshold.

    Parameters
    ----------
    event_tracks : Sequence[Graph]
      Containing the tracks of an event.
    track_Eth : float
      Track energy threshold.

    Returns
    -------
    A list of tuples containing (track_energy, track_length, track)
    for all the tracks with energy higher than threshold,
    ordered per track energy.
    """

    event_tracks_withE = []

    for i in range(len(event_tracks)):

        # Computing track energy
        track_E = sum(voxel.E for voxel in event_tracks[i])

        # If track energy >= threshold, append (track_E, track) to list
        # If not, iscarding tracks with track_E < threshold
        if track_E >= track_Eth:
            track_l = track_length(event_tracks[i])
            event_tracks_withE.append((track_E, track_l, event_tracks[i]))
        else:
            logger.debug('    Track with energy: {:6.1f} keV  -->  Discarded'
                         .format(track_E/units.keV))

    # Sorting tracks by their energies
    event_tracks_withE = sorted(event_tracks_withE, key=itemgetter(0), reverse=True)

    # VERBOSING
    logger.debug('  Sorted-Good Tracks ...')
    for i in range(len(event_tracks_withE)):
        logger.debug('    Track {}  energy: {:6.1f} keV   length: {:6.1f} mm'
                     .format(i, event_tracks_withE[i][0]/units.keV,
                             event_tracks_withE[i][1]/units.mm))

    return event_tracks_withE
