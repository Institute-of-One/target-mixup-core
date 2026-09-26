"""Manufactured CT/SEG control: independent closed-form expected values."""
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, CTImageStorage
from pydicom.sr.coding import Code
import highdicom as hd


def uid(name):
    return '2.25.' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://example.invalid/research-control/' + name).int)


def make_pair(destination, *, case_key='default', intensity_offset=0):
    if not isinstance(case_key, str) or not case_key:
        raise ValueError('Fixture key required')
    if type(intensity_offset) is not int or not -1000 <= intensity_offset <= 1000:
        raise ValueError('Fixture raw intensity offset out of range')
    def fixture_uid(name):
        return uid(name if case_key == 'default' else case_key + '/' + name)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    images=[]
    for z in range(3):
        meta=FileMetaDataset()
        meta.MediaStorageSOPClassUID=CTImageStorage
        meta.MediaStorageSOPInstanceUID=fixture_uid('ct-'+str(z))
        meta.TransferSyntaxUID=ExplicitVRLittleEndian
        d=FileDataset(None,{},file_meta=meta,preamble=b'\0'*128)
        d.SOPClassUID=CTImageStorage;d.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
        d.PatientID='SYNTHETIC-CONTROL-001';d.PatientName='Synthetic^Control'
        d.PatientBirthDate='';d.PatientSex='O'
        d.StudyInstanceUID=fixture_uid('study');d.SeriesInstanceUID=fixture_uid('ct-series')
        d.FrameOfReferenceUID=fixture_uid('frame');d.PositionReferenceIndicator=''
        d.StudyDate='20260923';d.StudyTime='120000';d.StudyID='CONTROL'
        d.AccessionNumber='';d.ReferringPhysicianName='';d.Modality='CT'
        d.SeriesNumber=1;d.InstanceNumber=z+1;d.Manufacturer='Synthetic research fixture'
        d.ImageType=['DERIVED','SECONDARY','AXIAL'];d.PatientPosition='HFS'
        d.SeriesDescription='SYNTHETIC NONCLINICAL analytic control'
        d.Rows=8;d.Columns=8;d.SamplesPerPixel=1;d.PhotometricInterpretation='MONOCHROME2'
        d.BitsAllocated=16;d.BitsStored=16;d.HighBit=15;d.PixelRepresentation=1
        d.PixelSpacing=[2,3];d.SliceThickness=4;d.SpacingBetweenSlices=4
        d.ImageOrientationPatient=[1,0,0,0,1,0];d.ImagePositionPatient=[10,20,30+4*z]
        d.RescaleSlope=2;d.RescaleIntercept=-100;d.RescaleType='HU';d.KVP=''
        y,x=np.indices((8,8));d.PixelData=(100*z+10*y+x+intensity_offset).astype('<i2').tobytes()
        images.append(d)
    mask=np.zeros((3,8,8),dtype=np.uint8);mask[0:2,1:3,2:4]=1
    algorithm=hd.AlgorithmIdentificationSequence(name='Analytic cuboid fixture',version='1',
        family=Code('CONTROL','99TEST','Synthetic control generator'))
    description=hd.seg.SegmentDescription(segment_number=1,segment_label='Synthetic cuboid',
        segmented_property_category=Code('CONTROL','99TEST','Synthetic control'),
        segmented_property_type=Code('CUBOID','99TEST','Analytic cuboid'),
        algorithm_type='AUTOMATIC',algorithm_identification=algorithm)
    seg=hd.seg.Segmentation(source_images=images,pixel_array=mask,segmentation_type='BINARY',
        segment_descriptions=[description],series_instance_uid=fixture_uid('seg-series'),series_number=2,
        sop_instance_uid=fixture_uid('seg'),instance_number=1,manufacturer='Synthetic research fixture',
        manufacturer_model_name='Analytic control',software_versions='1',device_serial_number='NONE',
        omit_empty_frames=False)
    def save(d,name):
        path=destination/name;d.save_as(path,enforce_file_format=True)
        return dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    pair=dict(patient=images[0].PatientID,
        ct=dict(metadata=dict(SeriesInstanceUID=fixture_uid('ct-series'),ImageCount=3),
                files=[save(d,f'ct_{i}.dcm') for i,d in enumerate(images)]),
        seg=dict(metadata=dict(SeriesInstanceUID=fixture_uid('seg-series'),ImageCount=1),files=[save(seg,'seg.dcm')]))
    return pair


if __name__=='__main__':
    from audit_rider import audit_pair
    from crosscheck_rider_readers import compare
    base=Path(__file__).parent
    pair=make_pair(base/'synthetic_control')
    result,_=audit_pair(pair)
    expected=dict(voxel_count=8,voxel_volume_mm3=24.0,roi_volume_ml=0.192,mean_rescaled_value=35.0)
    if not result['measurement_released'] or result['measurement'] != expected:
        raise AssertionError((result,expected))
    check=compare(pair)
    if not check['passed_pixel_crosscheck']:
        raise AssertionError(check)
    report=dict(kind='manufactured_DICOM_development_control',pair=pair,
        expected=expected,derivation='8 voxels; 2*3*4 mm3 each. Mean=2*(100*0.5+10*1.5+2.5)-100=35.',
        audit=result,reader_crosscheck=check,highdicom_version=hd.__version__,
        limitations='Not a patient, held-out benchmark, or comprehensive DICOM conformance certification.')
    (base/'synthetic_control_result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['measurement']))
